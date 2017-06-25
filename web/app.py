#!/usr/bin/env python

import os, sys, json
from dateutil import tz

from flask import Flask, request, render_template, url_for, make_response
from flask_httpauth import HTTPBasicAuth
from datetime import datetime
from dotenv import load_dotenv
import boto3
import pdfkit
import sqlite3 as lite

from product_names import products

app = Flask(__name__, static_url_path='')
auth = HTTPBasicAuth()

@auth.verify_password
def get_pw(username, password):
    user = os.environ['SMART_COOLER_LOGIN']
    pw = os.environ['SMART_COOLER_PASSWORD']
    return username == user and password == pw

@app.route("/")
@auth.login_required
def get_index():
    return app.send_static_file('index.html')

@app.route("/game")
def get_game():
    return app.send_static_file('game.html')

@app.route("/report")
@auth.login_required
def get_report():
    ts = request.args.get('ts')
    if ts:
        response = make_response(s3.Object(bucket_name, 'historical/' + ts + '/report_output.html').get()['Body'].read())
    else:
        response = make_response(s3.Object(bucket_name, 'report_output.html').get()['Body'].read())
    response.headers['Content-Type'] = 'text/html'
    return response

@app.route("/pdf")
@auth.login_required
def get_report_pdf():
    ts = request.args.get('ts')
    if ts:
        response = make_response(s3.Object(bucket_name, 'historical/' + ts + '/report_output.pdf').get()['Body'].read())
    else:
        response = make_response(s3.Object(bucket_name, 'report_output.pdf').get()['Body'].read())
    response.headers['Content-Type'] = 'application/pdf'
    return response

@app.route("/historical")
@auth.login_required
def get_historical():
    con = lite.connect('supercooler.db')
    with con:
        cur = con.cursor()
        cur.execute("SELECT * FROM Reports ORDER BY ts DESC")
        rows = cur.fetchall()
    con.close()
    return render_template('historical_template.html', reports=rows)

@app.route("/activity")
@auth.login_required
def get_activity():
    con = lite.connect('supercooler.db')
    with con:
        cur = con.cursor()
        cur.execute("SELECT * FROM Activity ORDER BY ts DESC")
        rows = cur.fetchall()

    con.close()
    return render_template('activity_template.html', activity=rows)

@app.route("/door_open")
def door_open():
    try:
        ts = request.args.get('timestamp')
    except Exception as e:
        return('cannot parse timestamp in params: {}'.format(e), 422)
    pretty_ts = adjust_timestamp(ts)
    if not upload_activity(ts, pretty_ts, 'open'):
        return('could not store door open event', 500)
    return('door open stored', 200)

@app.route("/door_close")
def door_close():
    try:
        ts = request.args.get('timestamp')
    except Exception as e:
        return('cannot parse timestamp in params: {}'.format(e), 422)
    pretty_ts = adjust_timestamp(ts)

    if not upload_activity(ts, pretty_ts, 'close'):
        return('could not store door close event', 500)
    return('door close stored', 200)

@app.route('/update')
def create_report():
    try:
        ts = request.args.get('timestamp')
    except Exception as e:
        return('invalid data sent: {}'.format(e), 422)

    try:
        upload = bool(request.args.get('upload'))
    except Exception as e:
        upload = False

    pretty_ts = adjust_timestamp(ts)

    try:
        data = request.args.get('data')
    except Exception as e:
        return('invalid data sent: {}'.format(e), 422)

    all_products = []
    shelf_map = {'D': 0, 'C': 1, 'B': 2, 'A': 3}
    shelfs = [
        { 'name': 'D', 'products': [] },
        { 'name': 'C', 'products': [] },
        { 'name': 'B', 'products': [] },
        { 'name': 'A', 'products': [] }
    ]

    try:
        json_data = json.loads(data)
    except Exception as e:
        return('cannot parse JSON: {}'.format(e), 422)

    for i in json_data:
        # check for valid shelf number
        shelf = i['shelf']
        if shelf == 'A' or shelf == 'B' or shelf == 'C' or shelf == 'D':
            shelfs[shelf_map[shelf]]['products'].append(i)
            all_products.append(i)
            for p in shelfs[shelf_map[shelf]]['products']:
                try:
                    p['name'] = products[str(p['type'])]['name']
                    p['src'] = products[str(p['type'])]['src']
                    p['width'] = float(products[str(p['type'])]['width'])
                except Exception as e:
                    return('Invalid key: {}, error: {}'.format(p['type'], e), 422)
        else:
            print('product not valid: {}'.format(i))

    shelf_counts = []
    for s in shelfs:
        shelf_counts.append(
            {
                'count': len(s['products']),
                'name': s['name']
            }
        )

    # create reference for sorted lists
    products_by_brand = {}
    for p in all_products:
        try:
            products_by_brand[p['name']]['count'] += 1
        except:
            products_by_brand[p['name']] = {}
            products_by_brand[p['name']]['count'] = 1
            products_by_brand[p['name']]['src'] = products[str(p['type'])]['src']

    # create sorted lists
    sorted_alpha = sorted(products_by_brand, key=str.lower)
    sorted_count = sorted(products_by_brand, key=products_by_brand.get, reverse=True)

    output_file = os.path.join('./static','report_output.html')
    with open(output_file, 'w') as f:
        try:
            html = render_template('report_template.html',
                ts=pretty_ts,
                shelfs=shelfs,
                shelf_counts=shelf_counts,
                all_products=all_products,
                products_by_brand=products_by_brand,
                sorted_alpha=sorted_alpha,
                sorted_count=sorted_count
            )
        except Exception as e:
            return('Cannot render HTML: {}'.format(e), 422)
        try:
            f.write(html)
        except Exception as e:
            return('Error writing file error: {}'.format(e), 422)

    if upload:
        uploaded = False
        if create_pdf():
            try:
                uploaded = upload_report(ts)
                print('uploaded reports')
            except Exception as e:
                return('Cannot upload report to S3: {}'.format(e), 422)

        if uploaded:
            if not store_reports(ts, pretty_ts, len(all_products)):
                return ('Was not able to store reports in database: {}'.format(e), 500)

    return ('{} products sent successfully'.format(len(all_products)), 200)

def store_reports(ts, pretty, product_count):
    con = None
    try:
        con = lite.connect('./supercooler.db')
        cur = con.cursor()
        cur.execute("INSERT INTO Reports VALUES(?, ?, ?)", (ts, pretty, product_count))
        cur.execute("INSERT INTO Activity VALUES(?, ?, ?)", (ts, pretty, 'scan'))
        con.commit()
    except lite.Error, e:
        print("Could not connect to database - {}:".format(e.args[0]))
        return False
    finally:
        if con:
            con.close()
    return True

def upload_report(ts):
    html_file_path = os.path.join('./static','report_output.html')
    html_name = 'report_output.html'
    pdf_file_path = os.path.join('./static','report_output.pdf')
    pdf_name = 'report_output.pdf'

    html_ts_path = 'historical/' + ts + '/report_output.html'
    pdf_ts_path = 'historical/' + ts + '/report_output.pdf'


    # upload html report
    try:
        print('uploading HTML')
        s3.Object(bucket_name, html_name).put(Body=open(html_file_path, 'rb'), ContentType='text/html')
    except Exception as e:
        print('could not upload html: {}'.format(e))
        return False

    # upload pdf report
    try:
        print('uploading PDF')
        s3.Object(bucket_name, pdf_name).put(Body=open(pdf_file_path, 'rb'), ContentType='application/pdf')
    except Exception as e:
        print('could not upload pdf: {}'.format(e))
        return False

    # upload historical reports
    try:
        print('uploading HTML and PDF')
        s3.Object(bucket_name, html_ts_path).put(Body=open(html_file_path, 'rb'), ContentType='text/html')
        s3.Object(bucket_name, pdf_ts_path).put(Body=open(pdf_file_path, 'rb'), ContentType='application/pdf')
    except Exception as e:
        print('could not upload html: {}'.format(e))
        return False

    return True

def create_pdf():
    input_html = os.path.join('./static','report_output.html')
    output_pdf = os.path.join('./static','report_output.pdf')
    options = { 'lowquality': None }
    try:
        pdfkit.from_file(input_html, output_pdf, options=options)
    except Exception as e:
        print('could not create PDF - {}'.format(e))
        return False
    return True

def adjust_timestamp(ts):
    utc_ts = datetime.fromtimestamp(int(ts))
    from_zone = tz.tzutc()
    to_zone = tz.gettz('America/New_York')
    utc_ts = utc_ts.replace(tzinfo=from_zone).astimezone(to_zone)
    return utc_ts.strftime('%H:%M:%S - %d %b %Y')

def upload_activity(ts, pretty_ts, type):
    con = None
    try:
        con = lite.connect('./supercooler.db')
        cur = con.cursor()
        cur.execute("INSERT INTO Activity VALUES(?, ?, ?)", (ts, pretty_ts, type))
        con.commit()
    except lite.Error, e:
        print('Could not connect to database - {}:'.format(e.args[0]))
        return False;
    finally:
        if con:
            con.close()
    return True

if __name__ == '__main__':
    # load env variables
    try:
        dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    except Exception as e:
        print ('cannot find .env file')
    load_dotenv(dotenv_path)

    # prepare s3
    bucket_name = "smart-fridge-dark-matter"
    aws_access_key_id = os.environ['SMART_COOLER_AWS_ACCESS_KEY_ID']
    aws_secret_access_key = os.environ['SMART_COOLER_AWS_SECRET_ACCESS_KEY']

    session = boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name="us-east-1"
    )
    s3 = session.resource("s3")

    port = 9000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    print('>> Using Port {}'.format(port))

    app.run(host='0.0.0.0', port=port, threaded=False)
