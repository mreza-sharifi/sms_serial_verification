from flask import Flask, jsonify, request, Response, redirect, url_for, session, abort
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
from pandas import read_excel
import sqlite3,re
import config

app = Flask(__name__)


# config
app.config.update(
    SECRET_KEY = config.SECRET_KEY
)

# flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"




# silly user model
class User(UserMixin):

    def __init__(self, id):
        self.id = id
        # self.name = "user" + str(id)
        # self.password = self.name + "_secret"
        
    def __repr__(self):
        return "%d" % (self.id)


# create some users with ids 1 to 20       
user = User(0)

@app.route('/')
@login_required
def home():
    return Response("Hello World!")

 
# somewhere to login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST': #TODO: stop the brute force
        username = request.form['username']
        password = request.form['password']        
        if password == config.PASSWORD and username == config.USERNAME:
            login_user(user)
            return redirect(request.args.get("next")) #TODO: check url validity
        else:
            return abort(401)
    else:
        return Response('''
        <form action="" method="post">
            <p><input type=text name=username>
            <p><input type=password name=password>
            <p><input type=submit value=Login>
        </form>
        ''')


# somewhere to logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return Response('<p>Logged out</p>')


# handle login failed
@app.errorhandler(401)
def page_not_found(error):
    return Response('<p>Login failed</p>')
     
    
# callback to reload the user object        
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


def normalize_string(data):
    from_char = '۰۱۲۳۴۵۶۷۸۹'
    to_char = '0123456789'
    for i in range(len(from_char)):
        data = data.replace(from_char[i], to_char[i])
    data = data.upper()
    data = re.sub(r'\W+', '', data) # remove any non alpha numeric  
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
        query = f'INSERT INTO serials (id, ref, desc, start_serial, end_serial, date) VALUES("{line}", "{ref}", "{desc}", "{start_serial}", "{end_serial}", "{date}");'
        cur.execute(query)
        # TODO: do some more error handling
        if serial_counter % 10 == 0:
            conn.commit()

        serial_counter += 1
        #print(line, ref, desc, start_serial, end_serial, date)
    conn.commit()

     # remove the invalids table if exists, then create new one
    cur.execute('DROP TABLE IF EXISTS invalids')
    cur.execute("""CREATE TABLE IF NOT EXISTS invalids (
        invalid_serial TEXT PRIMARY KEY);""")
    conn.commit()
    # now lets save the invalid serials
    df = read_excel(filepath, 1) # sheet 1 contain failed serial numbers.only one column  exists.
    invalid_counter = 0
    for index, (failed_serial, ) in df.iterrows():
        #failed_serial = failed_serial_row[0]

        query = f'INSERT INTO invalids VALUES("{failed_serial}");'
        cur.execute(query)
        # TODO: do some more error handling
        if invalid_counter % 10 == 0:
            conn.commit()

        invalid_counter += 1
    conn.commit()
    cur.close()
    return (serial_counter, invalid_counter)


def check_serial(serial):

    conn = sqlite3.connect(config.DATABASE_FILE_PATH)
    cur = conn.cursor()
    query = f"SELECT * FROM invalids WHERE invalid_serial == '{serial}'"
    results = cur.execute(query)
    if len(results.fetchall()) == 1:
        return 'this serial is among failed ones' # TODO: return the string provided by the cutomer
    
    query = f"SELECT * FROM serials WHERE start_serial < '{serial}' and end_serial > '{serial}'"
    #print(query)
    results = cur.execute(query)
    if len(results.fetchall()) == 1:
        return 'I found your serial' # TODO: return the string provided by the cutomer

    return 'it was not in the db'

@app.route('/v1/process', methods=['POST'])
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
    # send_sms('000', 'erfvs')
    import_database_from_excel('data.xlsx')
    #print(check_serial(normalize_string('jm200')))
    app.run("0.0.0.0", 5000, debug=True)
    #a,b = import_database_from_excel('data.xlsx')
    #print(f'inserted {a} rows and {b} invalids')