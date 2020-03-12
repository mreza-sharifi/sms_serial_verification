from flask import Flask, jsonify, request
import API_KEY
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
    print(f"message {message} recieved from {sender}")
    ret =  {"message": "processed"}
    return jsonify(ret), 200


def send_sms(receptor, message):
   """ this function will send sms
   """
   url = f'https://api.kavenegar.com/v1/{API-KEY}/sms/send.json'
   data = {"message": message,
           "receptor": receptor}
   responce= request.post(data)
   print(f"message *{message}* sent. status code os {responce.status_code}")

def check_serial():
    pass


if __name__ == "__main__":
    app.run("0.0.0.0", 5000, debug=True)
