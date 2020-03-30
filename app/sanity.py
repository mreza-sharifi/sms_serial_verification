# import MySQLdb
# import config



# def flash(message, level):
#     print(level, message)

# def get_database_connection():
#     """get connect to DB"""
#     return MySQLdb.connect(host=config.MYSQL_host, user=config.MYSQL_USERNAME, passwd=config.MYSQL_PASSWORD, db=config.MYSQL_DB_NAME, charset='utf8')


def colission(s1, e1, s2, e2):
    if s2 <= s1 <= e2:
        return True
    elif s2 <= e1 <= e2:
        return True
    elif s1 <= s2 <= e1:
        return True
    elif s1 <= e2 <= e1:
        return True
    return False
    




def seperate(input_string):
    """gets AA0000000000000000000000000090 and returns AA,90"""
    digit_part = ''
    alhpa_part = ''
    for character in input_string:
        if character.isalpha():
            alhpa_part += character
        elif character.isdigit():
            digit_part += character
    return alhpa_part, int(digit_part)


    db = get_database_connection()
    cur = db.cursor()


    cur.execute("SELECT id, start_serial, end_serial FROM serials")

    raw_data = cur.fetchall()

    data = {}
    for row in raw_data:
        id_row, start_serial, end_serial = row
        # print(id, start_serial, end_serial )
        start_serial_alpha , start_serial_digit = seperate(start_serial)
        end_serial_alpha , end_serial_digit = seperate(end_serial)
        if start_serial_alpha != end_serial_alpha:
            flash(f'Alpha parts of row {id_row} start with different letters', 'danger')
        else:
            if start_serial_alpha not in data:
                data[start_serial_alpha] = []
            data[start_serial_alpha].append((id_row, start_serial_digit, end_serial_digit))


    for letters in data:
        for i in range(len(data[letters])):
            for j in range(i+1, len(data[letters])):
                id_row1, ss1, es1 = data[letters][i]
                id_row2, ss2, es2 = data[letters][j]
                # print(letters, id_row1, id_row2, ss1, es1, ss2, es2)
                if colission(ss1, es1, ss2, es2):
                    flash(f'there is a colission in letter {letters}  between row ids {id_row1} and {id_row2}', 'danger')
