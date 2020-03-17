from flask import Flask, jsonify, request
from pandas import read_excel
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
    message = data["message"]
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



def import_database_from_excel(filepath):
    """gets an excel file name and imports lookup data (data and failures) from it """
    # df contains lookup data in the form of
    # Row	Reference Number	Description	Start Serial	End Serial	Date
    df = read_excel(filepath, 1)
    for index,(line, ref, desc, start_serial, end_serial, date) in df.iterrows():
        print(line, ref, desc, start_serial, end_serial, date)

    df = read_excel(filepath, 0) # sheet 1 contain failed serial numbers.only one column  exists.
    for index, (failed_serial) in df.iterrows():
        print(failed_serial[0])


def check_serial():
    pass


if __name__ == "__main__":
    # send_sms('000', 'erfvs')
    #app.run("0.0.0.0", 5000, debug=True)
    import_database_from_excel('data.xlsx')