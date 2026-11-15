HOSTINGER SHARED — AUREN BOOKING ENGINE
=========================================

This folder is the exact upload layout for public_html.

1. In hPanel create a MySQL database and database user. Assign the user to the database.
2. Upload the CONTENTS of this folder into public_html (not the folder itself).
3. In public_html/api, copy config.example.php to config.php.
4. Edit config.php on the server with the database details and two different long random secrets:
   - platform_token
   - default_admin_token
5. In hPanel select PHP 8.1+ and enable PDO MySQL and mbstring.
6. Enable SSL/HTTPS.
7. Open /health and confirm database=connected.
8. Customer portal: /web/
   Admin panel: /web/admin.html
9. Admin login workspace: default; token: the configured default_admin_token.

Do not upload api/config.php to GitHub or share its secrets. The API initializes its MySQL schema on first request. See docs/HOSTINGER-SHARED.md for full instructions and production safeguards.
