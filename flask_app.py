from bs4 import BeautifulSoup
from flask import Flask, request, flash, redirect, render_template, url_for, send_file
import requests
import os
import csv
import sys
from xlrd import open_workbook
import logging

app = Flask(__name__)
UPLOAD_FOLDER = '/home/davidwlok/mysite'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class Product:
    def __init__(self, local_id, vendor_url, vendor_variant, vendor_stock,
                 vendor_price, vendor_shipping, reference, compare_url,
                 compare_variant, compare_stock, compare_price,
                 compare_shipping, profit_formula, selling_formula,
                 reprice_store, reprice_sku, reprice_pause,
                 sales_price, estimated_profit, autoCompare):
        self.local_id = local_id
        self.vendor_url = vendor_url
        self.vendor_variant = vendor_variant
        self.vendor_stock = vendor_stock
        self.vendor_price = vendor_price
        self.vendor_shipping = vendor_shipping
        self.reference = reference
        self.compare_url = compare_url
        self.compare_variant = compare_variant
        self.compare_stock = compare_stock
        self.compare_price = compare_price
        self.compare_shipping = compare_shipping
        self.profit_formula = profit_formula
        self.selling_formula = selling_formula
        self.reprice_store = reprice_store
        self.reprice_sku = reprice_sku
        self.reprice_pause = reprice_pause
        self.sales_price = sales_price
        self.estimated_profit = estimated_profit
        self.autoCompare = autoCompare

def parse_products(products, percentage):
    percentage = float(percentage) * 0.01
    for product in products:
        match_found = False
        for sec_prod in products:
            if product == sec_prod:
                continue
            if product.reference == sec_prod.reference:
                match_found = True
                temp_prices = [float(product.sales_price),
                               float(sec_prod.sales_price)]
                lower_price = sorted(temp_prices)[0]
                minimum_offer = lower_price * percentage
                with open('/home/davidwlok/mysite/price_ref.csv', 'a') as csvfile:
                    csv_writer = csv.writer(csvfile)
                    csv_writer.writerow([
                        str(product.reference).replace('0', ''),
                        minimum_offer])
        if not match_found:
            minimum_offer = product.sales_price * percentage
            with open('/home/davidwlok/mysite/price_ref.csv', 'a') as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerow([
                    str(product.reference).replace('0', ''),
                    minimum_offer])
                #csv_writer.writerow([percentage])

def read_raw_data(file, percentage):
    products = []
    workbook = open_workbook(file)
    raw_data_sheet = workbook.sheets()[0]
    number_of_rows = raw_data_sheet.nrows
    number_of_columns = raw_data_sheet.ncols
    for row in range(1, number_of_rows):
        product = Product(
            *[raw_data_sheet.cell(row, i).value for i in range(0, number_of_columns)])
        product.reference = str(
            product.reference).split()[-1].split('.')[0]
        products.append(product)
    parse_products(products, percentage)

def create_http_session():
    """Creates requests.Session instance with properly set User-Agent header.
    Returns:
        requests.Session: Ready-to-go HTTP session.
    """
    session = requests.Session()
    session.headers.update({'User-Agent':
                            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/' +
                            '537.36 (KHTML, like Gecko) Chrome/58.0.3029.' +
                            '110 Safari/537.36',
                            })
    return session

class Item:
    def __init__(self, data, session):
        self.old_price = data['unitPrice']
        self.session = session
        self.url = 'https://www.homedepot.com' + data['pipSeoUrl']

    def get_details(self):
        #app.logger.info('URL')
        #app.logger.info(self.url)
        r = self.session.get(self.url)
        soup = BeautifulSoup(r.content, 'html.parser')
        self.new_price = soup.find('input',
            attrs={'id': 'ciItemPrice'}).get('value')
        self.name = soup.find('meta', attrs={'itemprop': 'name'}).get('content')
        self.old_price = float(self.old_price)
        self.new_price = float(self.new_price)


def search_order(order_id, email):
    string = ""
    session = create_http_session()
    r = session.post(
        'https://secure2.homedepot.com/customer/order/v1/guest/orderdetails',
        data='{"orderDetailsRequest":{"orderId":"%s","emailId":"%s"}}' \
        % (order_id, email),
    headers={'Content-Type': 'application/json'})
    try:
        response = r.json()['orderDetails']['lineItems']['lineItem']
    except KeyError:
        return "No order found with those details. Please try again."

    tempo_json = list()
    for item in response:
        i = Item(item, session)
        i.get_details()
        alert_status = False
        if i.old_price != i.new_price:
            alert_status = True
            string += '\n Price change detected for <a href="{3}">{0}</a>: Old price was {1}, current price is <b>{2}</b>.'.format(
                i.name, i.old_price, i.new_price, i.url).replace(' null ', '')

        tempo_json.append({
                'name':         i.name,
                'old_price':    i.old_price,
                'new_price':    i.new_price,
                'url':          i.url,
                'alert_status': alert_status
            })
    if string == "":
        string += "No price changes were found."
    return tempo_json


def create_file():
    with open('/home/davidwlok/mysite/price_ref.csv', 'w') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['item_id', 'min_offer'])


@app.route('/')
def hello_world():
    return render_template('index.html')


@app.route('/order-tracks', methods=['GET', 'POST'])
def home_depot():
    if request.method == 'POST':
        order_id = request.form['order_number']
        email = request.form['email']
        string = search_order(order_id, email)
        return render_template('orders_list.html', orders_data=string)
    #return render_template('index.html')


@app.route('/price_reference', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            create_file()
            try:
                percentage = float(request.form['text'])
            except ValueError:
                return "An invalid percentage or file-type was entered. Please try again."
            read_raw_data('/home/davidwlok/mysite/' + filename, percentage)
            try:
                return send_file('/home/davidwlok/mysite/price_ref.csv',
                                 mimetype='text/csv',
                                 attachment_filename='price_ref.csv',
                                 as_attachment=True)
            except ValueError:
                return "An invalid percentage or file-type was entered. Please try again."

    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <p><input type=file name=file>
               <input name=text>

         <input type=submit value=Upload>
    </form>
    '''


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            port = int(sys.argv[1])
        else:
            port = 9000
        app.secret_key = '8823EB36C2F8C82C935D3195E52BD'
        app.config['SESSION_TYPE'] = 'filesystem'
        app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
    except Exception as error:
        print("Could not parse command line: [{0}]".format(error))
        print("Expected usage: [python webserver_runner.py <PORT>")
        
