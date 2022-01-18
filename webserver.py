import errno
import traceback
import json
import cherrypy
import requests
import os
from pandas import json_normalize
import pytz
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from configparser import ConfigParser


class Counting:
    config = ConfigParser()
    config.read('config.ini')

    def process_datapush(self, datapush, header_data):
        for entry in datapush:
            type = entry.get('type', None)
            if type == 'LineCount':
                return self.attachment(header_data)

    def attachment(self, header_data):
        # Gather credentials from config.ini file
        config = ConfigParser()
        config.read('config.ini')
        sensor_uid = config['sensor']['user']
        sensor_pwd = config['sensor']['passwd']
        smtp_host = config['smtp']['host']
        smtp_pwd = config['smtp']['passwd']
        smtp_uid = config['smtp']['user']
        smtp_port = config['smtp']['port']
        # Start HTTPS Session with authentication
        with requests.Session() as session:
            session.auth = (sensor_uid, sensor_pwd)

            # Grabs the image and bypass SSL verification
            mac_addr = header_data
            response = session.get(f'https://ash.xovis.cloud/api/v1/devices/{mac_addr}/access/api/scene/live', verify=False)

        # Writes the PNG file to specified location
        filename = "C:\\code\\img\\sample_image.png"
        # If location does not exist, create it
        if not os.path.exists(os.path.dirname(filename)):
            try:
                os.makedirs(os.path.dirname(filename))
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise

        file = open(filename, "wb")
        file.write(response.content)
        file.close()
        print("PNG Downloaded")
        # Defines the date format, grabs the current time and converts to selected zone
        dt_format = "%d-%m-%Y %H:%M:%S"
        london_zone = datetime.now(pytz.timezone('Europe/London'))
        new_london = london_zone.strftime(dt_format)

        mail_from = smtp_uid
        mail_to = 'scott@ash.tech'
        mail_subject = 'Room 1 Alert - ' + new_london
        mail_body = '<p>++++++DO NOT REPLY TO THIS MAIL++++++</p><p>Single occupancy in Encryption Room - Zone 1 had been recorded for a duration of more than 30 seconds.</p><p>++++++DO NOT REPLY TO THIS MAIL++++++</p>'
        mail_attachment_name = "capture.png"

        mimemsg = MIMEMultipart()
        mimemsg['From'] = mail_from
        mimemsg['To'] = mail_to
        mimemsg['Subject'] = mail_subject
        mimemsg.attach(MIMEText(mail_body, 'html'))

        # Grabs the file earlier downloaded and stores it as an attachment to be sent
        with open(filename, "rb") as attachment:
            mimefile = MIMEBase('application', 'octet-stream')
            mimefile.set_payload(attachment.read())
            encoders.encode_base64(mimefile)
            mimefile.add_header('Content-Disposition', "attachment; filename = %s" % mail_attachment_name)
            mimemsg.attach(mimefile)
            connection = smtplib.SMTP(host=smtp_host, port=smtp_port)
            connection.starttls()
            connection.login(smtp_uid, smtp_pwd)
            connection.send_message(mimemsg)
            connection.quit()

class Webserver:

    def __init__(self, counting):
        self.__counting = counting

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['POST'])
    def push(self):
        try:
            # Extract MAC from header
            header_data = cherrypy.request.headers['MAC']
            # Handle the raw data from the body and convert to dataframe
            raw_data = cherrypy.request.body.read().decode('utf-8')
            parsed_data = json.loads(raw_data)
            db_data = json_normalize(parsed_data)
            print(db_data)
            # Pushes the MAC and Dataframe data to process_datapush inside the counting class
            self.__counting.process_datapush(parsed_data, header_data)

        except Exception:
            print("An Error occurred during datapush processing:\n{}".format(traceback.format_exc()))

if __name__ == '__main__':
    counting = Counting()

    # Cherrypy config
    conf = {
        '/': {
            'tools.sessions.on': False,
            'tools.staticdir.root': os.path.abspath(os.getcwd() + '/www')
        },
        'global': {
            'engine.autoreload.on': False,
            'server.socket_host': '0.0.0.0',
            'server.socket_port': 3080,

        }
    }

    # Start webserver
    cherrypy.quickstart(Webserver(counting), '/', conf)
