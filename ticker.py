#!/usr/bin/env python3
# Copyright (c) 2021 parazyd
# Copyright (c) 2020 llvll
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
Program to create a bitcoin ticker bitmap and show it on a waveshare 2in13_V2
eink screen (https://www.waveshare.com/wiki/2.13inch_e-Paper_HAT)
"""

import sys
from io import BytesIO
from json.decoder import JSONDecodeError
from os.path import join, dirname, realpath
from time import time, strftime, sleep
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import requests
mpl.use('Agg')

picdir = join(dirname(realpath(__file__)), 'images')
fontdir = join(dirname(realpath(__file__)), 'fonts')
font = ImageFont.truetype(join(fontdir, 'googlefonts/Roboto-Medium.ttf'), 40)
font_date = ImageFont.truetype(join(fontdir, 'PixelSplitter-Bold.ttf'), 11)

currency = 'usd'
coin = 'bitcoin'

tokenfilename = join(picdir, 'currency/%s.bmp' % currency)
athbitmap = Image.open(join(picdir, 'ATH.bmp'))
tokenimage = Image.open(tokenfilename)

API = 'https://api.coingecko.com/api/v3/coins'


def get_data(other):
    """ Grab data from API """
    days_ago = 7
    endtime = int(time())
    starttime = endtime - 60*60*24*days_ago

    geckourl = '%s/markets?vs_currency=%s&ids=%s' % (API, currency, coin)
    liveprice = requests.get(geckourl).json()[0]
    pricenow = float(liveprice['current_price'])
    alltimehigh = float(liveprice['ath'])
    other['volume'] = float(liveprice['total_volume'])

    url_hist = '%s/%s/market_chart/range?vs_currency=%s&from=%s&to=%s' % (
                     API, coin, currency, str(starttime), str(endtime))

    try:
        timeseriesarray = requests.get(url_hist).json()['prices']
    except JSONDecodeError:
        print('Caught JSONDecodeError')
        return None
    timeseriesstack = []
    length = len(timeseriesarray)
    i = 0
    while i < length:
        timeseriesstack.append(float(timeseriesarray[i][1]))
        i += 1

    timeseriesstack.append(pricenow)
    if pricenow > alltimehigh:
        other['ATH'] = True
    else:
        other['ATH'] = False
    return timeseriesstack


def make_spark(pricestack):
    """ Make a historical plot """
    _x = pricestack - np.mean(pricestack)
    fig, _ax = plt.subplots(1, 1, figsize=(10, 3))
    plt.plot(_x, color='k', linewidth=6)
    plt.plot(len(_x)-1, _x[-1], color='r', marker='o')

    for _, i in _ax.spines.items():
        i.set_visible(False)
    _ax.set_xticks = ([])
    _ax.set_yticks = ([])
    _ax.axhline(c='k', linewidth=4, linestyle=(0, (5, 2, 1, 2)))

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=17)
    buf.seek(0)
    imgspk = Image.open(buf)

    plt.clf()
    _ax.cla()
    plt.close(fig)
    return imgspk


def update_display(pricestack, sparkimage, other):
    """ Create an image from the data and send it to the display """
    days_ago = 7
    pricenow = pricestack[-1]

    if not other.get('lastprice'):
        other['lastprice'] = pricenow
    elif pricenow == other['lastprice']:
        return other

    other['lastprice'] = pricenow

    pricechange = str('%+d' % round(
        (pricestack[-1]-pricestack[0]) / pricestack[-1]*100, 2))+'%'
    if pricenow > 1000:
        pricenowstring = format(int(pricenow), ',')
    else:
        pricenowstring = str(float('%.5g' % pricenow))

    image = Image.new('L', (250, 122), 255)
    draw = ImageDraw.Draw(image)
    if other['ATH'] is True:
        print('%s (ATH!)' % pricenowstring)
        image.paste(athbitmap, (15, 30))
    else:
        print(pricenowstring)
        image.paste(tokenimage, (0, 15))

    image.paste(sparkimage, (80, 15))
    draw.text((130, 66), str(days_ago) + 'day : ' + pricechange,
              font=font_date, fill=0)
    draw.text((96, 73), '$'+pricenowstring, font=font, fill=0)

    draw.text((95, 5), str(strftime('%H:%M %a %d %b %Y')), font=font_date,
              fill=0)

    display_eink(image)

    return other


def display_eink(image):
    """ Wrapper to display or show image """
    if epd:
        epd.display(epd.getbuffer(image))
    else:
        image.show()


def close_epd():
    """ Cleanup for epd context """
    if not epd:
        return
    epd.sleep()
    epd.Dev_exit()
    # epd2in13_V2.epdconfig.module_exit()


def main():
    """ main routine """
    def fullupdate():
        other = {}
        pricestack = get_data(other)
        if not pricestack:
            return time()
        sparkimage = make_spark(pricestack)
        other = update_display(pricestack, sparkimage, other)
        return time()

    try:
        data_pulled = False
        lastcoinfetch = time()

        while True:
            if (time() - lastcoinfetch > float(60)) or data_pulled is False:
                lastcoinfetch = fullupdate()
                data_pulled = True
            sleep(5)
    except KeyboardInterrupt:
        close_epd()
        return 1

    return 1


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '-d':
        epd = None  # pylint: disable=C0103
    else:
        from waveshare_epd import epd2in13_V2  # pylint: disable=E0401
        epd = epd2in13_V2.EPD()
        epd.init(epd.FULL_UPDATE)
        epd.Clear(0xFF)
    sys.exit(main())
