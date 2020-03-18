from flask import Flask, jsonify, request
from pandas import read_excel
import sqlite3
import config

app = Flask(__name__)


@app.route('/v1/process', methods=['POST'])
def process():
    """this is a callback from kavenegar. will get sender and message
    and will check if it is valid. then answer back
    """
    data = request.form
    # import pdb; pdb.set_trace()
    sender = data["from"]
    message = normalize_string(data["message"])
    print(f'message {message} recieved from {sender}')
    send_sms(sender, 'Hi '+message)
    ret =  {"message": "processed"}
    return jsonify(ret), 200


def send_sms(receptor, message):
    """ this function will send sms
    """
    url = 'https://api.kavenegar.com/v1/{config.API-KEY}/sms/send.json'
    data = {"message": message,
            "receptor": receptor}
    res= request.post(data)
    print(f"message *{message}* sent. status code os {res.status_code}")


def normalize_string(str):
    from_char = '۰۱۲۳۴۵۶۷۸۹'
    to_char = '0123456789'
    for i in range(len(from_char)):
        str = str.replace(from_char[i], to_char[i])
    str = str.upper()
    return(str)





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
def check_serial():
    pass


if __name__ == "__main__":
    # send_sms('000', 'erfvs')
    #app.run("0.0.0.0", 5000, debug=True)
    a,b = import_database_from_excel('data.xlsx')
    print(f'inserted {a} rows and {b} invalids')