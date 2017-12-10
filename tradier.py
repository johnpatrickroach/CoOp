import sys
import urllib2
import xml.etree.ElementTree as ET
import pandas as pd

ticker = sys.argv[1]
token = "s7k6EyMKkSTGwxoWBz9zyiOq3fUU"

def getchain(ti,to):
    expdates = []
    optionslist = []

    quoteurl = "https://sandbox.tradier.com/v1/markets/quotes?symbols={SYMBOL}".format(SYMBOL=ti)
    quotereq = urllib2.Request(quoteurl)
    quotereq.add_header('Authorization', 'Bearer %s' % to)
    quotexml = urllib2.urlopen(quotereq)
    quotexml = ET.fromstring(quotexml.read())
    quote = quotexml.find('quote')
    last = quote.find('last')
    currentprice = last.text

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
            strike = option.find('strike').text
            last = option.find('last').text
            bid = option.find('bid').text
            ask = option.find('ask').text
            change = option.find('change').text
            open_interest = option.find('open_interest').text
            row = {'ticker': ti, 'current price': currentprice, 'symbol': symbol, 'expiration': date, 'strike': strike, 'last': last, 'bid': bid, 'ask': ask, 'change': change, 'open_interest': open_interest}
            optionslist.append(row)
    optionsdf = pd.DataFrame(optionslist)
    optionsdf = optionsdf[['ticker', 'current price', 'symbol', 'expiration', 'strike', 'last', 'bid', 'ask', 'change', 'open_interest']]
    print optionsdf

optionsdf = getchain(ti=ticker,to=token)
