<?php
/**
 * Copy this file to config.php on the server.
 * Never commit config.php or paste its secrets into chat.
 */
return [
    'db_host' => 'localhost',
    'db_port' => 3306,
    'db_name' => 'YOUR_HOSTINGER_DATABASE_NAME',
    'db_user' => 'YOUR_HOSTINGER_DATABASE_USER',
    'db_password' => 'REPLACE_WITH_DATABASE_PASSWORD',
    // Generate two different random strings (at least 40 characters each).
    'platform_token' => 'REPLACE_WITH_LONG_RANDOM_PLATFORM_SECRET',
    'default_admin_token' => 'REPLACE_WITH_DIFFERENT_LONG_RANDOM_DEFAULT_ADMIN_SECRET',
];
