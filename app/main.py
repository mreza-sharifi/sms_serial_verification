import os
import re
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from pandas import read_excel
import MySQLdb
from flask import Flask, jsonify, request, Response, redirect, url_for, abort,flash,render_template
from werkzeug.utils import secure_filename
import requests
import config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3

UPLOAD_FOLDER = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
limiter = Limiter(
    app,
    key_func=get_remote_address)

# config
app.config.update(
    SECRET_KEY = config.SECRET_KEY
)

# flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"
db=MySQLdb.connect(host=config.MYSQL_host, user=config.MYSQL_USERNAME, passwd=config.MYSQL_PASSWORD,db=config.MYSQL_DB_NAME)

CALL_BACK_TOKEN = config.CALL_BACK_TOKEN

# silly user model
class User(UserMixin):

    def __init__(self, id):
        self.id = id
        # self.name = "user" + str(id)
        # self.password = self.name + "_secret"
        
    def __repr__(self):
        return "%d" % (self.id)

user = User(0)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
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
    
    return render_template('index.html')
 
# somewhere to login
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    # flash('Please Log in', 'info')
    if current_user.is_authenticated:
        return redirect('/')
    if request.method == 'POST': #TODO: stop the brute force
        username = request.form['username']
        password = request.form['password']        
        if password == config.PASSWORD and username == config.USERNAME:
            login_user(user)
            return redirect('/') #TODO: check url validity
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
    flash('Login Problem', 'danger')
    return redirect('/login')
     
@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404  
# callback to reload the user object 
#       
@login_manager.user_loader
def load_user(userid):
    return User(userid)
    
@app.route('/v1/ok')
def health_check():
    ret = {'message': 'ok'}
    return jsonify(ret), 200




def send_sms(receptor, message):
    """ this function will send sms
    """
    url = 'https://api.kavenegar.com/v1/{config.API-KEY}/sms/send.json'
    data = {"message": message,
            "receptor": receptor}
    res= request.post(data)
    print(f"message *{message}* sent. status code os {res.status_code}")


def normalize_string(data,fixed_size=30):
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
    for c in data:
        if c.isalpha():
            all_alpha += c
        elif c.isdigit():
            all_digit += c
    missing_zeros = fixed_size - len(all_digit) - len(all_alpha)
    data = all_alpha + '0'*missing_zeros + all_digit
    return(data)





def import_database_from_excel(filepath):
    """gets an excel file name and imports lookup data (data and failures) from it 
        the (1) sheet contains serial data like:
         Row	Reference_Number	Description	Start_Serial	End_Serial	Date
         and the (0) contains a column of invalid serials.
         This data will be wrriten into the qlite database located at config.DATABASE_FILE_PATH
        in two tables."serials" and "invalids" 
        
        return two integers: (number of serial rows, number of invalid rows)
        
        """
    # df contains lookup data in the form of

    # Row	Reference Number	Description	Start Serial	End Serial	Date
    
    # TODO: make sure that the data is imported correctly, we need to backup the old one.
    # TODO: do some normalization
    ## our sqlite database will contain two tables: serials and invalids
    conn = sqlite3.connect(config.DATABASE_FILE_PATH)
    cur = conn.cursor()
    # remove the serials table if exists, then create new one
    cur.execute('DROP TABLE IF EXISTS serials')
    cur.execute("""CREATE TABLE IF NOT EXISTS serials (
        id INTEGER PRIMARY KEY,
        ref TEXT,
        desc TEXT,
        start_serial TEXT,
        end_serial TEXT,
        date DATE);""")
    
    df = read_excel(filepath, 0)
    serial_counter = 0
    for index,(line, ref, desc, start_serial, end_serial, date) in df.iterrows():
        start_serial = normalize_string(start_serial)
        end_serial = normalize_string(end_serial)
        #print((line, ref, desc, start_serial, end_serial, date))
        #query = f'INSERT INTO serials (id, ref, desc, start_serial, end_serial, date) VALUES("{line}", "{ref}", "{desc}", "{start_serial}", "{end_serial}", "{date}");'
        cur.execute("INSERT INTO serials VALUES (?, ?, ?, ?, ?, ?)", (line, ref, desc, start_serial, end_serial, str(date)))
        #cur.execute("INSERT INTO PROCESSED_SMS (status, sender, message, answer, date) VALUES (%s, %s, %s, %s, %s)", (status, sender, message, answer, now))

        #print(query)
        #cur.execute(query)
        # TODO: do some more error handling
        if serial_counter % 10 == 0:
            conn.commit()

        serial_counter += 1
        #print(line, ref, desc, start_serial, end_serial, date)
    conn.commit()

     # remove the invalids table if exists, then create new one
    cur.execute('DROP TABLE IF EXISTS invalids')
    cur.execute("""CREATE TABLE IF NOT EXISTS invalids (
        invalid_serial TEXT);""")
    conn.commit()
    # now lets save the invalid serials
    df = read_excel(filepath, 1) # sheet 1 contain failed serial numbers.only one column  exists.
    invalid_counter = 0
    for index, (failed_serial, ) in df.iterrows():
        #failed_serial = failed_serial_row[0]
        failed_serial = normalize_string(failed_serial)
        #query = f'INSERT INTO invalids VALUES("{failed_serial}");'
        cur.execute('INSERT INTO invalids VALUES (?)', (failed_serial, ))
        #cur.execute(query)
        # TODO: do some more error handling
        if invalid_counter % 10 == 0:
            conn.commit()

        invalid_counter += 1
    conn.commit()
    cur.close()
    return (serial_counter, invalid_counter)


def check_serial(serial):
    ''' this function will check the serial'''
    conn = sqlite3.connect(config.DATABASE_FILE_PATH)
    cur = conn.cursor()
    #query = f"SELECT * FROM invalids WHERE invalid_serial == '{serial}'"
    serial = normalize_string(serial)
    results = cur.execute("SELECT * FROM invalids WHERE invalid_serial == ?", (serial, ))
    #results = cur.execute(query)
    if len(results.fetchall()) > 0:
        return 'this serial is among failed ones' # TODO: return the string provided by the cutomer
    
    #query = f"SELECT * FROM serials WHERE start_serial <= '{serial}' and end_serial >= '{serial}'"
    results = cur.execute("SELECT * FROM serials WHERE start_serial <= ? and end_serial >= ?", (serial, serial))

    #print(query)
    #results = cur.execute(query)
    if len(results.fetchall()) == 1:
        return 'I found your serial' # TODO: return the string provided by the cutomer

    return 'it was not in the db'

@app.route(f'/v1/{CALL_BACK_TOKEN}/process', methods=['POST'])
def process():
    """this is a callback from kavenegar. will get sender and message
    and will check if it is valid. then answer back
    """
    data = request.form
    # import pdb; pdb.set_trace()
    sender = data["from"]
    message = normalize_string(data["message"])
    print(f'message {message} recieved from {sender}') # logging
    answer = check_serial(message)
    send_sms(sender, answer)
    ret =  {"message": "processed"}
    return jsonify(ret), 200
if __name__ == "__main__":
    import_database_from_excel('data.xlsx')
    check_serial('JJ100')
    app.run("0.0.0.0", 5000, debug=True)