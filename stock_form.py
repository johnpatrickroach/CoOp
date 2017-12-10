from flask import Flask, render_template, flash, request, redirect, url_for
from wtforms import Form, TextField, TextAreaField, validators, StringField, SubmitField
import sys
import urllib2
import xml.etree.ElementTree as ET
import pandas as pd
import datetime as dt

pd.set_option('display.float_format', lambda x: '%.2f' % x)

#App config
DEBUG = True
app = Flask(__name__)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = 'optionstest'

class ReusableForm(Form):
    ticker = TextField('Ticker:', validators=[validators.required()])


@app.route("/", methods=['GET', 'POST'])
def stock_form_post():
    form = ReusableForm(request.form)

    print form.errors
    if request.method == 'POST':
        ticker=request.form['ticker']
        print ticker

        if form.validate():
            flash('Getting the options chain and calculating the metrics for %s...' % ticker)
            ti = ticker
            to = "s7k6EyMKkSTGwxoWBz9zyiOq3fUU"
            expdates = []
            calls = []
            puts = []
            combos = []
            errors = []

            quoteurl = "https://sandbox.tradier.com/v1/markets/quotes?symbols={SYMBOL}".format(SYMBOL=ti)
            quotereq = urllib2.Request(quoteurl) # CHANGE TO REQUEST
            quotereq.add_header('Authorization', 'Bearer %s' % to)
            quotexml = urllib2.urlopen(quotereq)
            quotexml = ET.fromstring(quotexml.read())
            quote = quotexml.find('quote')
            last = quote.find('last')
            currentprice = float(last.text)

            expurl = "https://sandbox.tradier.com/v1/markets/options/expirations?symbol={SYMBOL}".format(SYMBOL=ti)
            expreq = urllib2.Request(expurl)
            expreq.add_header('Authorization', 'Bearer %s' % to)
            expxml = urllib2.urlopen(expreq)
            expxml = ET.fromstring(expxml.read())
            for date in expxml.findall('date'):
                expdates.append(date.text)

            for date in expdates:
                chainurl = "https://sandbox.tradier.com/v1/markets/options/chains?symbol={SYMBOL}&expiration={DATE}".format(SYMBOL=ti,DATE=date)
                chainreq = urllib2.Request(chainurl)
                chainreq.add_header('Authorization', 'Bearer %s' % to)
                chainxml = urllib2.urlopen(chainreq)
                chainxml = ET.fromstring(chainxml.read())
                options = chainxml.findall('option')
                for option in options:
                    symbol = option.find('symbol').text
                    optype = symbol[10]
                    if optype == 'C':
                        optype = 'Call'
                    elif optype == 'P':
                        optype = 'Put'
                    else:
                        optype == 'Error'
                    strike = option.find('strike').text
                    if strike == None:
                        continue
                    else:
                        strike = float(strike)
                    #last = option.find('last').text
                    #if last == None:
                    #    continue
                    #if last != None:
                    #    last = float(last)
                    bid = option.find('bid').text
                    if bid == None or bid == '0.0' or bid == 0.0:
                        continue
                    else:
                        bid = float(bid)
                    ask = option.find('ask').text
                    if ask == None or ask == '0.0' or ask == 0.0:
                        continue
                    else:
                        ask = float(ask)
                    #change = option.find('change').text
                    #if change != None:
                    #    change = float(change)
                    #open_interest = option.find('open_interest').text
                    #if open_interest != None:
                    #    open_interest = float(open_interest)
                    date1 = dt.datetime.today().date()
                    date2 = dt.datetime.strptime(date, "%Y-%m-%d").date()
                    delta = date2 - date1
                    days = delta.days
                    row = {'ticker': ti, 'current price': currentprice, 'symbol': symbol, 'type': optype, 'expiration': date, 'strike': strike, 'bid': bid, 'ask': ask, 'days': days}
                    if optype == 'Call':
                        calls.append(row)
                    elif optype == 'Put':
                        puts.append(row)
                    else:
                        errors.append(row)
            callsdf = pd.DataFrame(calls)
            #callsdf[(callsdf != 'None').all(1)]
            callsdf = callsdf[['ticker', 'current price', 'symbol', 'type', 'expiration', 'strike', 'bid', 'ask', 'days']]
            for call in calls:
                for put in puts:
                    if call['expiration'] == put['expiration']:
                        combo = {'ticker': call['ticker'], 'current price': call['current price'], 'symbol': call['symbol'], 'expiration': call['expiration'], 'call cost': call['bid'], 'call strike': call['strike'], 'put cost': put['ask'], 'put strike': put['strike'], 'days': call['days']}
                        combos.append(combo)
                    else:
                        continue
            combosdf = pd.DataFrame(combos)
            combosdf = combosdf[['ticker', 'current price', 'symbol', 'expiration', 'call cost', 'call strike', 'put cost', 'put strike', 'days']]

            callsdf.rename(columns={'bid':'call cost'}, inplace=True)

            #[ if current price > call strike > put strike ] == [ (current price) + call cost + (put cost) + call strike ]
            #[ if call strike > current price > put strike ] == [ (current price) + call cost + (put cost) + current price ]
            #[ if call strike > put strike > current price ] == [ (current price) + call cost + (put cost) + put strike ]
            #[ if current price > put strike > call strike ] == [ (current price) + call cost + (put cost) + call strike ]
            #[ if put strike > current price > call strike ] == [ (current price) + call cost + (put cost) + call strike ]
            #[ if put strike > call strike > current price ] == [ (current price) + call cost + (put cost) + put strike ]

            combosdf['if flat'] = (-1*combosdf['current price'])+(combosdf['call cost'])+(-1*combosdf['put cost'])
            combosdf['if flat'] = combosdf.apply(lambda x: (x['if flat']+x['current price']) if (x['call strike'] > x['current price'] > x['put strike']) else ((x['if flat']+x['put strike']) if (x['call strike'] > x['put strike'] > x['current price']) else ((x['if flat']+x['put strike']) if (x['put strike'] > x['call strike'] > x['current price']) else x['call strike'])), axis=1)
            combosdf['if flat %'] = (combosdf['if flat']/(-1*((-1*combosdf['current price'])+(combosdf['call cost'])+(-1*combosdf['put cost']))))
            combosdf['if -15%'] = (-1*combosdf['current price'])+(combosdf['call cost'])+(-1*combosdf['put cost'])+(.85*combosdf['current price'])
            combosdf['if -15% (%)'] = (combosdf['if -15%']/(-1*((-1*combosdf['current price'])+(combosdf['call cost'])+(-1*combosdf['put cost']))))
            combosdf['if -30%'] = (-1*combosdf['current price'])+(combosdf['call cost'])+(-1*combosdf['put cost'])+(.70*combosdf['current price'])
            combosdf['if -30% (%)'] = (combosdf['if -30%']/(-1*((-1*combosdf['current price'])+(combosdf['call cost'])+(-1*combosdf['put cost']))))
            combosdf['if -50%'] = (-1*combosdf['current price'])+(combosdf['call cost'])+(-1*combosdf['put cost'])+(.5*combosdf['current price'])
            combosdf['if -50% (%)'] = (combosdf['if -50%']/(-1*((-1*combosdf['current price'])+(combosdf['call cost'])+(-1*combosdf['put cost']))))
            combosdf['Max Loss @ Stock Price'] = combosdf['put strike']
            combosdf['Percent Stock Price'] = ((combosdf['Max Loss @ Stock Price']+combosdf['current price'])/combosdf['current price'])
            combosdf['Gain Stops'] = combosdf['call strike']
            combosdf['Gain Protected'] = ((combosdf['Gain Stops']+combosdf['current price'])/combosdf['current price'])
            combosdf['Protected Chances'] = ((combosdf['Percent Stock Price'])*(combosdf['Gain Protected']))
            combosdf['RiskReward'] = ((combosdf['Protected Chances'])*(combosdf['if flat %'])/combosdf['days'])
            combosdf=combosdf.sort_values(by='RiskReward',ascending=False)
            combosdf = combosdf[combosdf.RiskReward > 0]

            callsdf['if flat'] = (-1*callsdf['current price'])+(callsdf['call cost'])+(callsdf['current price'])
            callsdf['if flat %'] = (callsdf['if flat']/(-1*((-1*callsdf['current price'])+(callsdf['call cost']))))
            callsdf['if -15%'] = (-1*callsdf['current price'])+(callsdf['call cost'])+(.85*callsdf['current price'])
            callsdf['if -15% (%)'] = (callsdf['if -15%']/(-1*((-1*callsdf['current price'])+(callsdf['call cost']))))
            callsdf['if -30%'] = (-1*callsdf['current price'])+(callsdf['call cost'])+(.70*callsdf['current price'])
            callsdf['if -30% (%)'] = (callsdf['if -30%']/(-1*((-1*callsdf['current price'])+(callsdf['call cost']))))
            callsdf['if -50%'] = (-1*callsdf['current price'])+(callsdf['call cost'])+(.5*callsdf['current price'])
            callsdf['if -50% (%)'] = (callsdf['if -50%']/(-1*((-1*callsdf['current price'])+(callsdf['call cost']))))
            #callsdf['Max Loss @ Stock Price'] = callsdf['put strike']
            #callsdf['Percent Stock Price'] = ((callsdf['Max Loss @ Stock Price']+callsdf['current price'])/callsdf['current price'])*100
            callsdf['Percent Stock Price'] = -1
            callsdf['Gain Stops'] = callsdf['strike']
            callsdf['Gain Protected'] = ((callsdf['Gain Stops']+callsdf['current price'])/callsdf['current price'])
            callsdf['Protected Chances'] = ((callsdf['Percent Stock Price'])*(callsdf['Gain Protected']))
            callsdf['RiskReward'] = ((callsdf['Protected Chances'])*(callsdf['if flat %'])/callsdf['days'])
            callsdf=callsdf.sort_values(by='RiskReward',ascending=False)
            callsdf = callsdf[callsdf.RiskReward > 0]

            return render_template('chain.html', tables=[combosdf.to_html(classes='combos'), callsdf.to_html(classes='calls')],
            titles = ['na', '%s Options Chain' % ti])
        else:
            flash('All the form fields are required. ')

    return render_template('view.html', form=form)

if __name__ == '__main__':
    app.run()

#@app.route('/')
#def stock_form():
#    return render_template("index.html")
#
#@app.route('/', methods=['POST'])
#def stock_form_post():
#    ticker = request.form['stock']
#    ticker = ticker.upper()
#    os.system("python tradier.py %s" % ticker)
#
#if __name__ == '__main__':
#    app.debug = True
#    app.run()
