API_KEY = ""
# call back url from kavenegar look like '/v1/{CALL_BACK_TOKEN}/process'
CALL_BACK_TOKEN = 'arsyhvinutrvy843vbt983u95798ucnjkhuih34h98te' 
SECRET_KEY= 'slkrgjldbnU^V%^&U%&U^I$C%U&%*V&^I%IB*^(*^NO(NIB656565#$$#&$&$$@#@$!#BET$WBW$YBYWVTWBTVCEC'

DATABASE_FILE_PATH = 'data.sqlite'
USERNAME = 'root'
PASSWORD = 'root'

# generate one strong string key for flask

UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'xlsx'}
MYSQL_host='localhost'
MYSQL_USERNAME='root'
MYSQL_PASSWORD='test'
MYSQL_DB_NAME = 'smsmysql'


# create table PROCESSED_SMS (status ENUM('OK', 'FAILURE', 'DOUBLE', 'NOT-FOUND'),sender CHAR(20), message VARCHAR(400), answer VARCHAR(400),date DATETIME ,INDEX(date, status));
# CREATE TABLE IF NOT EXISTS serials (id INTEGER PRIMARY KEY,ref VARCHAR(200),descripton VARCHAR(200), start_serial VARCHAR(30),end_serial VARCHAR(30),date DATETIME);