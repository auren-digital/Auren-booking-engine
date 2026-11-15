<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

function respond(mixed $data, int $status = 200): never {
    http_response_code($status);
    if ($status === 204) exit;
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
    exit;
}
function fail(int $status, string $detail): never { respond(['detail'=>$detail],$status); }
function nowUtc(): string { return gmdate('Y-m-d\TH:i:s.u\Z'); }
function hashToken(string $token): string { return hash('sha256',$token); }
function requestHeaders(): array {
    $headers=function_exists('getallheaders')?getallheaders():[];
    foreach($_SERVER as $key=>$value) if(str_starts_with($key,'HTTP_')) {
        $name=str_replace(' ','-',ucwords(strtolower(str_replace('_',' ',substr($key,5)))));
        $headers[$name]??=$value;
    }
    return array_change_key_case($headers,CASE_LOWER);
}
function headerValue(array $headers,string $name):?string {
    $value=$headers[strtolower($name)]??null;
    return is_string($value)&&trim($value)!==''?trim($value):null;
}
function bodyJson():array {
    $raw=file_get_contents('php://input');
    if($raw===false||trim($raw)==='')return [];
    $data=json_decode($raw,true);
    if(!is_array($data))fail(400,'Request body must be valid JSON.');
    return $data;
}
function requiredString(array $data,string $key,int $min,int $max):string {
    $value=$data[$key]??null;
    if(!is_string($value))fail(422,"$key must be a string.");
    $value=trim($value);$length=mb_strlen($value);
    if($length<$min||$length>$max)fail(422,"$key length must be between $min and $max.");
    return $value;
}
function optionalString(array $data,string $key,int $max):?string {
    if(!array_key_exists($key,$data)||$data[$key]===null)return null;
    if(!is_string($data[$key]))fail(422,"$key must be a string.");
    $value=trim($data[$key]);if(mb_strlen($value)>$max)fail(422,"$key is too long.");
    return $value===''?null:$value;
}
function positiveInt(mixed $value,string $field,int $max=10000,int $default=1):int {
    if($value===null)$value=$default;
    if(filter_var($value,FILTER_VALIDATE_INT)===false)fail(422,"$field must be an integer.");
    $number=(int)$value;if($number<1||$number>$max)fail(422,"$field must be between 1 and $max.");
    return $number;
}
function boolValue(mixed $value,string $field):bool {
    if(is_bool($value))return $value;
    if($value===0||$value===1||$value==='0'||$value==='1')return (bool)$value;
    fail(422,"$field must be a boolean.");
}
function utcDate(mixed $value,string $field):string {
    if(!is_string($value)||!preg_match('/(?:Z|[+-]\d{2}:\d{2})$/i',$value))fail(422,"$field must include a timezone offset.");
    try{return (new DateTimeImmutable($value))->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s.u');}
    catch(Throwable){fail(422,"$field must be a valid datetime.");}
}
function isoDate(?string $value):?string {
    if($value===null||$value==='')return null;
    try{return (new DateTimeImmutable($value,new DateTimeZone('UTC')))->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s.u\Z');}
    catch(Throwable){return $value;}
}
function reservationOut(array $row):array {
    foreach(['start_at','end_at','created_at'] as $field)$row[$field]=isoDate($row[$field]??null);
    $row['quantity']=(int)$row['quantity'];unset($row['tenant_id']);return $row;
}
function resourceOut(array $row):array {
    $row['capacity']=(int)$row['capacity'];$row['is_active']=(bool)$row['is_active'];return $row;
}

$configPath=__DIR__.'/config.php';
if(!is_file($configPath))fail(503,'API is not configured. Copy api/config.example.php to api/config.php and enter database credentials.');
$config=require $configPath;
if(!is_array($config))fail(500,'Invalid API configuration.');
try{
    $dsn=sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4',$config['db_host']??'localhost',(int)($config['db_port']??3306),$config['db_name']??'');
    $pdo=new PDO($dsn,(string)($config['db_user']??''),(string)($config['db_password']??''),[
        PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false
    ]);
    $pdo->exec("SET time_zone = '+00:00'");
}catch(Throwable $e){error_log('AUREN Booking DB connection failed: '.$e->getMessage());fail(503,'Database connection unavailable. Check the private API configuration.');}

function initializeSchema(PDO $pdo,array $config):void {
    $pdo->exec("CREATE TABLE IF NOT EXISTS tenants (
        id VARCHAR(63) PRIMARY KEY, slug VARCHAR(63) NOT NULL UNIQUE, name VARCHAR(120) NOT NULL,
        admin_token_hash CHAR(64) NOT NULL UNIQUE, created_at DATETIME(6) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
    $pdo->exec("CREATE TABLE IF NOT EXISTS resources (
        id VARCHAR(120) NOT NULL, tenant_id VARCHAR(63) NOT NULL, name VARCHAR(120) NOT NULL,
        category VARCHAR(40) NOT NULL DEFAULT 'general', capacity INT NOT NULL DEFAULT 1,
        is_active TINYINT(1) NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL,
        PRIMARY KEY (tenant_id,id), CONSTRAINT fk_resources_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
    $pdo->exec("CREATE TABLE IF NOT EXISTS reservations (
        id CHAR(36) PRIMARY KEY, reference_code VARCHAR(20) NOT NULL, tenant_id VARCHAR(63) NOT NULL,
        resource_id VARCHAR(120) NOT NULL, customer_name VARCHAR(200) NOT NULL, customer_email VARCHAR(254) NULL,
        start_at DATETIME(6) NOT NULL, end_at DATETIME(6) NOT NULL,
        status ENUM('confirmed','cancelled','completed') NOT NULL DEFAULT 'confirmed',
        notes VARCHAR(2000) NULL, quantity INT NOT NULL DEFAULT 1, created_at DATETIME(6) NOT NULL,
        UNIQUE KEY uq_tenant_reference (tenant_id,reference_code),
        KEY idx_reservation_range (tenant_id,resource_id,status,start_at,end_at),
        CONSTRAINT fk_reservations_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id),
        CONSTRAINT fk_reservations_resource FOREIGN KEY (tenant_id,resource_id) REFERENCES resources(tenant_id,id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
    $defaultToken=(string)($config['default_admin_token']??'');
    if($defaultToken==='')fail(503,'Set default_admin_token in api/config.php before using the API.');
    $stmt=$pdo->prepare("INSERT IGNORE INTO tenants (id,slug,name,admin_token_hash,created_at) VALUES ('default','default','Default Workspace',?,UTC_TIMESTAMP(6))");
    $stmt->execute([hashToken($defaultToken)]);
    $seed=[['vehicle-1','Vehículo 1','vehicle'],['room-1','Habitación 1','room'],['room-2','Habitación 2','room'],['service-1','Servicio 1','service']];
    $stmt=$pdo->prepare("INSERT IGNORE INTO resources (id,tenant_id,name,category,capacity,is_active,created_at) VALUES (?, 'default', ?, ?, 1, 1, UTC_TIMESTAMP(6))");
    foreach($seed as $item)$stmt->execute($item);
}
try {
    $check = $pdo->query("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name IN ('tenants','resources','reservations')")->fetchColumn();
    $defaultExists = false;
    if ((int)$check === 3) {
        $defaultExists = (bool)$pdo->query("SELECT 1 FROM tenants WHERE id='default' LIMIT 1")->fetchColumn();
    }
    if ((int)$check !== 3 || !$defaultExists) initializeSchema($pdo,$config);
} catch(Throwable $e) {
    error_log('AUREN Booking schema init failed: '.$e->getMessage());
    fail(500,'Database schema initialization failed.');
}

function requireTenant(PDO $pdo,?string $tenantId):string {
    if(!$tenantId||!preg_match('/^[a-z0-9][a-z0-9-]{1,62}$/',$tenantId))fail(400,'A valid X-Tenant-ID header is required.');
    $stmt=$pdo->prepare('SELECT id FROM tenants WHERE id=?');$stmt->execute([$tenantId]);$row=$stmt->fetch();
    if(!$row)fail(404,'Workspace not found.');return $row['id'];
}
function requireAdmin(PDO $pdo,?string $token):string {
    if(!$token)fail(401,'Missing administrative token.');
    $stmt=$pdo->prepare('SELECT id FROM tenants WHERE admin_token_hash=?');$stmt->execute([hashToken($token)]);$row=$stmt->fetch();
    if(!$row)fail(401,'Invalid administrative token.');return $row['id'];
}
function requirePlatform(array $config,?string $token):void {
    $expected=(string)($config['platform_token']??'');
    if($expected==='')fail(503,'Platform provisioning is disabled. Configure platform_token.');
    if(!$token||!hash_equals($expected,$token))fail(401,'Invalid platform token.');
}
function seedResources(PDO $pdo,string $tenantId):void {
    $seed=[['vehicle-1','Vehículo 1','vehicle'],['room-1','Habitación 1','room'],['room-2','Habitación 2','room'],['service-1','Servicio 1','service']];
    $stmt=$pdo->prepare('INSERT INTO resources (id,tenant_id,name,category,capacity,is_active,created_at) VALUES (?,?,?,?,1,1,UTC_TIMESTAMP(6))');
    foreach($seed as $item)$stmt->execute([$item[0],$tenantId,$item[1],$item[2]]);
}
function getReservation(PDO $pdo,string $id,string $tenantId):array {
    $stmt=$pdo->prepare('SELECT * FROM reservations WHERE id=? AND tenant_id=?');$stmt->execute([$id,$tenantId]);$row=$stmt->fetch();
    if(!$row)fail(404,'Reservation not found.');return reservationOut($row);
}

$headers=requestHeaders();$method=strtoupper($_SERVER['REQUEST_METHOD']??'GET');
$uriPath=parse_url($_SERVER['REQUEST_URI']??'/',PHP_URL_PATH)?:'/';$path=rtrim($uriPath,'/')?:'/';
if($method==='OPTIONS')respond(null,204);
$tenantHeader=headerValue($headers,'x-tenant-id');$adminHeader=headerValue($headers,'x-admin-token');
$platformHeader=headerValue($headers,'x-platform-token');$input=bodyJson();

if($method==='GET'&&$path==='/health'){$pdo->query('SELECT 1')->fetch();respond(['status'=>'ok','service'=>'auren-booking-engine','version'=>'0.6.0','database'=>'connected','timestamp'=>nowUtc()]);}
if($method==='GET'&&$path==='/api/v1')respond(['service'=>'AUREN Booking Engine','version'=>'0.6.0','status'=>'operational','multi_tenant'=>true,'docs'=>null,'health'=>'/health','customer_portal'=>'/web/index.html','admin_portal'=>'/web/admin.html']);

if($method==='POST'&&$path==='/api/v1/platform/tenants'){
    requirePlatform($config,$platformHeader);$name=requiredString($input,'name',2,120);$slug=requiredString($input,'slug',2,63);
    if(!preg_match('/^[a-z0-9][a-z0-9-]+$/',$slug))fail(422,'slug has an invalid format.');
    $token=rtrim(strtr(base64_encode(random_bytes(36)),'+/','-_'),'=');$pdo->beginTransaction();
    try{$stmt=$pdo->prepare('INSERT INTO tenants (id,slug,name,admin_token_hash,created_at) VALUES (?,?,?,?,UTC_TIMESTAMP(6))');$stmt->execute([$slug,$slug,$name,hashToken($token)]);seedResources($pdo,$slug);$pdo->commit();}
    catch(PDOException $e){if($pdo->inTransaction())$pdo->rollBack();if($e->getCode()==='23000')fail(409,'A workspace with this slug already exists.');error_log('AUREN tenant create failed: '.$e->getMessage());fail(500,'Could not create workspace.');}
    respond(['id'=>$slug,'name'=>$name,'admin_token'=>$token,'created_at'=>nowUtc()],201);
}
if($method==='GET'&&$path==='/api/v1/public/resources'){
    $tenantId=requireTenant($pdo,$tenantHeader);$s=$pdo->prepare('SELECT id,name,category,capacity,is_active FROM resources WHERE tenant_id=? AND is_active=1 ORDER BY name');$s->execute([$tenantId]);respond(array_map('resourceOut',$s->fetchAll()));
}
if($method==='GET'&&$path==='/api/v1/resources'){
    $tenantId=requireAdmin($pdo,$adminHeader);$s=$pdo->prepare('SELECT id,name,category,capacity,is_active FROM resources WHERE tenant_id=? ORDER BY name');$s->execute([$tenantId]);respond(array_map('resourceOut',$s->fetchAll()));
}
if($method==='POST'&&$path==='/api/v1/resources'){
    $tenantId=requireAdmin($pdo,$adminHeader);$id=requiredString($input,'id',2,120);
    if(!preg_match('/^[A-Za-z0-9][A-Za-z0-9_-]+$/',$id))fail(422,'id has an invalid format.');
    $name=requiredString($input,'name',2,120);$category=requiredString($input,'category',2,40);$capacity=positiveInt($input['capacity']??1,'capacity');
    try{$s=$pdo->prepare('INSERT INTO resources (id,tenant_id,name,category,capacity,is_active,created_at) VALUES (?,?,?,?,?,1,UTC_TIMESTAMP(6))');$s->execute([$id,$tenantId,$name,$category,$capacity]);}
    catch(PDOException $e){if($e->getCode()==='23000')fail(409,'A resource with this ID already exists in the workspace.');fail(500,'Could not create resource.');}
    respond(['id'=>$id,'name'=>$name,'category'=>$category,'capacity'=>$capacity,'is_active'=>true],201);
}
if($method==='PUT'&&preg_match('#^/api/v1/resources/([^/]+)$#',$path,$m)){
    $tenantId=requireAdmin($pdo,$adminHeader);$id=rawurldecode($m[1]);$updates=[];
    foreach(['name','category','capacity','is_active'] as $key)if(array_key_exists($key,$input)){
        if($key==='name')$updates[$key]=requiredString($input,$key,2,120);
        elseif($key==='category')$updates[$key]=requiredString($input,$key,2,40);
        elseif($key==='capacity')$updates[$key]=positiveInt($input[$key],$key);
        else $updates[$key]=boolValue($input[$key],$key)?1:0;
    }
    if(!$updates)fail(422,'Provide at least one field to update.');
    $pdo->beginTransaction();$s=$pdo->prepare('SELECT id,name,category,capacity,is_active FROM resources WHERE tenant_id=? AND id=? FOR UPDATE');$s->execute([$tenantId,$id]);$current=$s->fetch();
    if(!$current){$pdo->rollBack();fail(404,'Resource not found.');}
    $newCapacity=$updates['capacity']??(int)$current['capacity'];
    if($newCapacity<(int)$current['capacity']){
        $q=$pdo->prepare("SELECT start_at,end_at,quantity FROM reservations WHERE tenant_id=? AND resource_id=? AND status='confirmed'");$q->execute([$tenantId,$id]);$events=[];
        foreach($q->fetchAll() as $r){$events[]=[$r['start_at'],1,(int)$r['quantity']];$events[]=[$r['end_at'],0,(int)$r['quantity']];}
        usort($events,fn($a,$b)=>($a[0]<=>$b[0])?:($a[1]<=>$b[1]));$active=0;
        foreach($events as $event){$active+=$event[1]===1?$event[2]:-$event[2];if($active>$newCapacity){$pdo->rollBack();fail(409,'Capacity cannot be lower than existing confirmed bookings.');}}
    }
    $sets=[];$values=[];foreach($updates as $key=>$value){$sets[]=$key.' = ?';$values[]=$value;}
    $values[]=$tenantId;$values[]=$id;$s=$pdo->prepare('UPDATE resources SET '.implode(',',$sets).' WHERE tenant_id=? AND id=?');$s->execute($values);$pdo->commit();
    $s=$pdo->prepare('SELECT id,name,category,capacity,is_active FROM resources WHERE tenant_id=? AND id=?');$s->execute([$tenantId,$id]);respond(resourceOut($s->fetch()));
}
if($method==='GET'&&$path==='/api/v1/public/availability'){
    $tenantId=requireTenant($pdo,$tenantHeader);$resourceId=(string)($_GET['resource_id']??'');$start=utcDate($_GET['start_at']??null,'start_at');$end=utcDate($_GET['end_at']??null,'end_at');
    if($end<=$start)fail(422,'end_at must be later than start_at');$quantity=positiveInt($_GET['quantity']??1,'quantity');
    $s=$pdo->prepare('SELECT id,capacity,is_active FROM resources WHERE tenant_id=? AND id=?');$s->execute([$tenantId,$resourceId]);$resource=$s->fetch();
    if(!$resource||!(bool)$resource['is_active'])fail(404,'Resource not found or inactive.');
    $s=$pdo->prepare("SELECT COALESCE(SUM(quantity),0) total FROM reservations WHERE tenant_id=? AND resource_id=? AND status='confirmed' AND start_at<? AND end_at>?");$s->execute([$tenantId,$resourceId,$end,$start]);$booked=(int)$s->fetch()['total'];$remaining=max(0,(int)$resource['capacity']-$booked);
    respond(['resource_id'=>$resourceId,'capacity'=>(int)$resource['capacity'],'booked'=>$booked,'remaining'=>$remaining,'requested'=>$quantity,'available'=>$remaining>=$quantity]);
}
if($method==='POST'&&$path==='/api/v1/reservations'){
    $tenantId=requireTenant($pdo,$tenantHeader);$resourceId=requiredString($input,'resource_id',1,120);$quantity=positiveInt($input['quantity']??1,'quantity');
    $customerName=requiredString($input,'customer_name',1,200);$email=optionalString($input,'customer_email',254);
    if($email!==null&&!filter_var($email,FILTER_VALIDATE_EMAIL))fail(422,'customer_email must be a valid email.');
    $start=utcDate($input['start_at']??null,'start_at');$end=utcDate($input['end_at']??null,'end_at');if($end<=$start)fail(422,'end_at must be later than start_at');
    $notes=optionalString($input,'notes',2000);$id=strtolower(implode('-', [bin2hex(random_bytes(4)),bin2hex(random_bytes(2)),bin2hex(random_bytes(2)),bin2hex(random_bytes(2)),bin2hex(random_bytes(6))]));
    $reference='AUR-'.strtoupper(bin2hex(random_bytes(4)));$created=nowUtc();$pdo->beginTransaction();
    try{
        $s=$pdo->prepare('SELECT id,capacity FROM resources WHERE tenant_id=? AND id=? AND is_active=1 FOR UPDATE');$s->execute([$tenantId,$resourceId]);$resource=$s->fetch();
        if(!$resource){$pdo->rollBack();fail(422,'Resource not found or inactive for this workspace.');}
        $s=$pdo->prepare("SELECT COALESCE(SUM(quantity),0) total FROM reservations WHERE tenant_id=? AND resource_id=? AND status='confirmed' AND start_at<? AND end_at>?");$s->execute([$tenantId,$resourceId,$end,$start]);$booked=(int)$s->fetch()['total'];
        if($booked+$quantity>(int)$resource['capacity']){$pdo->rollBack();fail(409,'Insufficient remaining capacity for this time range.');}
        $s=$pdo->prepare("INSERT INTO reservations (id,reference_code,tenant_id,resource_id,customer_name,customer_email,start_at,end_at,status,notes,quantity,created_at) VALUES (?,?,?,?,?,?,?,?, 'confirmed',?,?,?)");
        $s->execute([$id,$reference,$tenantId,$resourceId,$customerName,$email,$start,$end,$notes,$quantity,gmdate('Y-m-d H:i:s.u')]);$pdo->commit();
    }catch(PDOException $e){if($pdo->inTransaction())$pdo->rollBack();error_log('AUREN reservation create failed: '.$e->getMessage());fail(500,'Could not create reservation.');}
    respond(['id'=>$id,'reference_code'=>$reference,'resource_id'=>$resourceId,'customer_name'=>$customerName,'customer_email'=>$email,'quantity'=>$quantity,'start_at'=>isoDate($start),'end_at'=>isoDate($end),'status'=>'confirmed','notes'=>$notes,'created_at'=>$created],201);
}
if($method==='GET'&&$path==='/api/v1/reservations'){
    $tenantId=requireAdmin($pdo,$adminHeader);$sql='SELECT * FROM reservations WHERE tenant_id=?';$params=[$tenantId];
    if(isset($_GET['resource_id'])&&$_GET['resource_id']!==''){$sql.=' AND resource_id=?';$params[]=(string)$_GET['resource_id'];}
    if(isset($_GET['reservation_status'])&&$_GET['reservation_status']!==''){
        if(!in_array($_GET['reservation_status'],['confirmed','cancelled','completed'],true))fail(422,'Invalid reservation_status.');$sql.=' AND status=?';$params[]=(string)$_GET['reservation_status'];
    }
    $sql.=' ORDER BY start_at';$s=$pdo->prepare($sql);$s->execute($params);respond(array_map('reservationOut',$s->fetchAll()));
}
if($method==='GET'&&preg_match('#^/api/v1/public/reservations/([^/]+)$#',$path,$m)){
    $tenantId=requireTenant($pdo,$tenantHeader);$folio=strtoupper(rawurldecode($m[1]));$email=trim((string)($_GET['email']??''));
    if(mb_strlen($email)<3||mb_strlen($email)>254)fail(422,'email length must be between 3 and 254.');
    $s=$pdo->prepare('SELECT * FROM reservations WHERE tenant_id=? AND reference_code=? AND LOWER(customer_email)=LOWER(?)');$s->execute([$tenantId,$folio,$email]);$row=$s->fetch();
    if(!$row)fail(404,'Reservation not found. Check the folio and email.');respond(reservationOut($row));
}
if($method==='POST'&&preg_match('#^/api/v1/reservations/([^/]+)/cancel$#',$path,$m)){
    $tenantId=requireAdmin($pdo,$adminHeader);$id=rawurldecode($m[1]);$pdo->beginTransaction();
    $s=$pdo->prepare('SELECT * FROM reservations WHERE id=? AND tenant_id=? FOR UPDATE');$s->execute([$id,$tenantId]);$row=$s->fetch();
    if(!$row){$pdo->rollBack();fail(404,'Reservation not found.');}
    if($row['status']==='completed'){$pdo->rollBack();fail(409,'Completed reservations cannot be cancelled.');}
    if($row['status']!=='cancelled'){$s=$pdo->prepare("UPDATE reservations SET status='cancelled' WHERE id=? AND tenant_id=?");$s->execute([$id,$tenantId]);}
    $pdo->commit();respond(getReservation($pdo,$id,$tenantId));
}
fail(404,'Endpoint not found.');
