import os
import re
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from pandas import read_excel
import MySQLdb
from textwrap import dedent
from flask import Flask, jsonify, request, Response, redirect, url_for, abort, flash, render_template
from werkzeug.utils import secure_filename
import requests
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import config
# import sqlite3
MAX_FLASH = 10
UPLOAD_FOLDER = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
limiter = Limiter(app, key_func=get_remote_address)

# config
app.config.update(SECRET_KEY=config.SECRET_KEY)

# flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"

CALL_BACK_TOKEN = config.CALL_BACK_TOKEN

class User(UserMixin):
    def __init__(self, id):
        self.id = id

    def __repr__(self):
        return "%d" % (self.id)

user = User(0)
@login_manager.user_loader
def load_user(userid):
    return User(userid)

def allowed_file(filename):
    """check allowed file"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    """return home page.
    check serial.
    upload file.
    show messages"""
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            rows, failures = import_database_from_excel(file_path)
            flash(f'Imported {rows} rows of serials and {failures} rows of failure', 'success')
            os.remove(file_path)
            return redirect('/')
    database = get_database_connection()
    cur = database.cursor() 
    cur.execute("SELECT * FROM PROCESSED_SMS ORDER BY date DESC LIMIT 5000;")
    all_smss = cur.fetchall()
    smss = []
    for sms in all_smss:
        status, sender, message, answer, date = sms
        smss.append({'status':status, 'sender':sender,
                     'message':message, 'answer':answer, 'date':date})
    
    cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'OK';")
    num_ok = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'FAILURE';")
    num_failure = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'DOUBLE';")
    num_double = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM PROCESSED_SMS WHERE status = 'NOT-FOUND';")
    num_not_found = cur.fetchone()[0]
    database.close()
    return render_template('index.html', data={'smss':smss, 'ok':num_ok,
                                               'failure':num_failure, 'double':num_double,
                                               'not_found':num_not_found})
 
# somewhere to login
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    # flash('Please Log in', 'info')
    if current_user.is_authenticated:
        return redirect('/')
    if request.method == 'POST': 
        username = request.form['username']
        password = request.form['password']        
        if password == config.PASSWORD and username == config.USERNAME:
            login_user(user)
            return redirect('/')
        else:
            return abort(401)
    else:
        return render_template('login.html')


# somewhere to logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Logged Out', 'success')
    return redirect('/login')


# handle login failed
@app.errorhandler(401)
def login_problem(error):
    """check login problem"""
    flash('Login Problem', 'danger')
    return redirect('/login')


@app.errorhandler(404)
def page_not_found(error):
    """return 404 page"""
    return render_template('404.html'), 404  


@app.route('/v1/ok')
def health_check():
    """very simple.the system will return ok if the system is ok.for monitoring usage"""
    ret = {'message': 'ok'}
    return jsonify(ret), 200


def send_sms(receptor, message):
    """ this function will send sms
    """
    url = 'https://api.kavenegar.com/v1/{config.API-KEY}/sms/send.json'
    data = {"message": message,
            "receptor": receptor}
    res = request.post(data)
    print(f"message *{message}* sent. status code os {res.status_code}")


def normalize_string(data, fixed_size=30):
    """this function will normalize the messages"""

    from_persian_char = '۱۲۳۴۵۶۷۸۹۰'
    from_arabic_char = '١٢٣٤٥٦٧٨٩٠'
    to_char = '1234567890'
    for i in range(len(to_char)):
        data = data.replace(from_persian_char[i], to_char[i])
        data = data.replace(from_arabic_char[i], to_char[i])
    data = data.upper()
    data = re.sub(r'\W+', '', data) # remove any non alpha numeric  
    all_alpha = ''
    all_digit = ''
    for this_char in data:
        if this_char.isalpha():
            all_alpha += this_char
        elif this_char.isdigit():
            all_digit += this_char
    missing_zeros = fixed_size - len(all_digit) - len(all_alpha)
    data = all_alpha + '0'*missing_zeros + all_digit
    return data

def import_database_from_excel(filepath):
    """gets an excel file name and imports lookup data (data and failures) from it 
        the (1) sheet contains serial data like:
         Row	Reference_Number	descriptonription	Start_Serial	End_Serial	Date
         and the (0) contains a column of invalid serials.
         This data will be wrriten into the qlite database located at config.DATABASE_FILE_PATH
        in two tables."serials" and "invalids"
        return two integers: (number of serial rows, number of invalid rows)
        """
    # df contains lookup data in the form of
    # Row,Reference Number,descriptonription,Start Serial,End Serial,Date
    database = get_database_connection()

    cur = database.cursor() 
    # remove the serials table if exists, then create new one
    try:
        cur.execute('DROP TABLE IF EXISTS serials;')
        cur.execute("""CREATE TABLE IF NOT EXISTS serials (
            id INTEGER PRIMARY KEY,
            ref VARCHAR(200),
            descripton VARCHAR(200),
            start_serial CHAR(30),
            end_serial CHAR(30),
            date DATETIME, INDEX(start_serial, end_serial));""")
        database.commit()
    except Exception as e:
        flash('problem dropping and creating new serial table in database {e}', 'danger')
 
    data_frame = read_excel(filepath, 0)
    serial_counter = 0
    line_number = 0
    total_flashes = 0
    for _ , (line, ref, descripton, start_serial, end_serial, date) in data_frame.iterrows():
        line_number += 1
        try:
            start_serial = normalize_string(start_serial)
            end_serial = normalize_string(end_serial)
            cur.execute("INSERT INTO serials VALUES (%s, %s, %s, %s, %s, %s);", 
                        (line, ref, descripton, start_serial, end_serial, date))
            database.commit()
            serial_counter += 1
        except Exception as e:
            total_flashes += 1
            if total_flashes < MAX_FLASH:
                flash(f'Error inserting line {line_number} from serials sheet 0 {e}', 'danger')
            elif total_flashes == MAX_FLASH:
                flash(f'Too many errors', 'danger')
            
        database.commit()

    try:
        cur.execute('DROP TABLE IF EXISTS invalids;')
        cur.execute("""CREATE TABLE IF NOT EXISTS invalids (
            invalid_serial CHAR(200), INDEX(invalid_serial));""")
        database.commit()
    except Exception as e:
        flash('Error Dropping and creating invalid table {e}', 'danger')
    # now lets save the invalid serials
    data_frame = read_excel(filepath, 1) # sheet 1 contain failed serial numbers.only one column  exists.
    invalid_counter = 0
    line_number = 0
    for _, (failed_serial, ) in data_frame.iterrows():
        line_number += 1
        try:
            failed_serial = normalize_string(failed_serial)        
            cur.execute('INSERT INTO invalids VALUES (%s);', (failed_serial, ))
            database.commit()
            invalid_counter += 1
        except Exception as e:
            total_flashes += 1
            if total_flashes < MAX_FLASH:
                flash(f'Error inserting line {line_number} from failures sheet 1 {e}', 'danger')
            elif total_flashes == MAX_FLASH:
                flash(f'Too many errors', 'danger')
   
    database.close()
    return (serial_counter, invalid_counter)


def check_serial(serial):
    ''' this function will check the serial'''
    original_serial = serial
    serial = normalize_string(serial)
    database = get_database_connection()
    
    #cur = database.cursor()       
    with database.cursor() as cur:
        results = cur.execute("SELECT * FROM invalids WHERE invalid_serial = %s", (serial, ))
        if results > 0:
            answer = dedent(f"""\
                    {original_serial}
                    این شماره هولوگرام یافت نشد. لطفا دوباره سعی کنید  و یا با واحد پشتیبانی تماس حاصل فرمایید.
                    ساختار صحیح شماره هولوگرام بصورت دو حرف انگلیسی و 7 یا 8 رقم در دنباله آن می باشد. مثال:
                    FA1234567
                    شماره تماس با بخش پشتیبانی فروش شرکت التک:
                    021-22038385""")
            # database.close()
            return 'FAILURE', answer 
        results = cur.execute("SELECT * FROM serials WHERE start_serial <= %s and end_serial >= %s", (serial, serial))

        if results > 1:
            ret = cur.fetchone()
            answer = dedent(f"""\
                    {original_serial}
                    این شماره هولوگرام مورد تایید است.
                    برای اطلاعات بیشتر از نوع محصول با بخش پشتیبانی فروش شرکت التک تماس حاصل فرمایید:
                    021-22038385""")
            return 'DOUBLE', answer
        if results == 1:
            ret = cur.fetchone()
            desc = ret[2]
            ref_number = ret[1]
            date = ret[5].date()
            answer = dedent(f"""\
                    {original_serial}
                    {ref_number}
                    {desc}
                    Hologram date: {date}
                    Genuine product of Schneider Electric
                    شماره تماس با بخش پشتیبانی فروش شرکت التک:
                    021-22038385""")
            return 'OK', answer
        # database.close()
        answer = dedent(f"""\
                    {original_serial}
                    این شماره هولوگرام یافت نشد. لطفا دوباره سعی کنید  و یا با واحد پشتیبانی تماس حاصل فرمایید.
                    ساختار صحیح شماره هولوگرام بصورت دو حرف انگلیسی و 7 یا 8 رقم در دنباله آن می باشد. مثال:
                    FA1234567
                    شماره تماس با بخش پشتیبانی فروش شرکت التک:
                    021-22038385""")
        return 'NOT-FOUND', answer

@app.route("/check_one_serial", methods=['POST'])
@login_required
def check_one_serial():
    """the function will check answer of the message in DB and set status of it"""
    serial_to_check = request.form["serial"]
    status, answer = check_serial(serial_to_check)
    flash(f'{status} - {answer}', 'info')

    return redirect('/')


@app.route(f'/v1/{CALL_BACK_TOKEN}/process', methods=['POST'])
def process(sender, message):
    """this is a callback from kavenegar. will get sender and message
    and will check if it is valid. then answer back
    # """
    # data = request.form
    # # import pdb; pdb.set_trace()
    # sender = data["from"]
    # message = data["message"]
    print(f'message {message} recieved from {sender}') # logging
    status, answer = check_serial(message)
    database = get_database_connection()
    cur = database.cursor() 
    now = datetime.now()
    formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("INSERT INTO PROCESSED_SMS (status, sender, message, answer, date) VALUES (%s, %s, %s, %s, %s)",
                (status, sender, message, answer, formatted_date))
    print(f"INSERT INTO PROCESSED_SMS (status, sender, message, answer, date) VALUES (%s, %s, %s, %s, %s)",
                (status, sender, message, answer, formatted_date))
    database.commit()
    database.close()
    # send_sms(sender, answer)
    # ret = {"message": "processed"}
    # return jsonify(ret), 200


def get_database_connection():
    """get connect to DB"""
    return MySQLdb.connect(host=config.MYSQL_host, user=config.MYSQL_USERNAME, passwd=config.MYSQL_PASSWORD, db=config.MYSQL_DB_NAME, charset='utf8')


if __name__ == "__main__":
    import_database_from_excel('data.xlsx')
    ss = ['','1','A','JM0000000000000000000000000109','JM101'
    'JM104','JJ321',
    'Jj000121']
    
    for s in ss:
        # print(s,check_serial(s))
        process('sender', s)

    app.run("0.0.0.0", 5000, debug=True)