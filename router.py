#!/usr/bin/python3

import http.client
import urllib.parse
import json


class Address(object):
    def __init__(self, dictaddress):
        self.dictaddress = dictaddress

    def getaddressstr(self):
        addrstr = "%s %s, %s, %s" % (self.dictaddress['house_number'],
                                     self.dictaddress['road'],
                                     self.dictaddress['city'],
                                     self.dictaddress['country'] )
        return addrstr

    def getshortaddressstr(self):
        addrstr = "%s %s, %s" % (self.dictaddress['house_number'],
                                 self.dictaddress['road'],
                                 self.dictaddress['city'] )
        return addrstr


class Router:
    """Returns a rout between to points on a map

    fromLatLng - from tuple of (latitude, longitude)
    toLatLng - to tuple of (latitude, longitude)
    transport - the type of transport, possible options are: motorcar, bicycle or foot. Default is: motorcar.
    """
    def __init__(self, fromlatlng, tolatlng, transport='motorcar'):
        self.jsonroutedata = None
        print('create Router with %s->%s' % (fromlatlng, tolatlng))
        conn = http.client.HTTPConnection("www.yournavigation.org")
        params = urllib.parse.urlencode({'format': 'geojson',
                                         'flon': fromlatlng[1], 'flat': fromlatlng[0],
                                         'tlon': tolatlng[1], 'tlat': tolatlng[0],
                                         'v': transport, 'fast': '1',
                                         'layer': 'mapnik', 'instructions': 1})

        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/html",
                   "X-Yours-client": "oren@orengampel.com  testing"}
        try:
            conn.request("GET", "/api/1.0/gosmore.php?" + params)
        except IOError as IOe:
            print("connection to server failed: " + str(IOe))

        response = conn.getresponse()
        print(response.status, response.reason)
        d1 = response.read()
        self.jsonroutedata = json.loads(d1.decode('utf8'))
        conn.close()

    """Return the original JSON data"""

    def getjson(self):
        return self.jsonroutedata

    """Return travel time"""
    def getTravelTime(self):
        if self.jsonroutedata:
            return self.jsonroutedata['properties']['traveltime']
        else:
            return

    """Return travel time in minutes"""
    def getTravelTimeMin(self):
        if self.jsonroutedata:
            return int(self.jsonroutedata['properties']['traveltime']) / 60
        else:
            return

    """Return distance"""
    def getDistance(self):
        if self.jsonroutedata:
            return self.jsonroutedata['properties']['distance']
        else:
            return

    def getPath(self):
        if self.jsonroutedata:
            return [coordinate[::-1] for coordinate in self.jsonroutedata['coordinates']]

    @staticmethod
    def getgoecode(textaddress, limit=5, lang='he,en'):
        """Return latlng of a textual address.

        :rtype : json
        :param textaddress: the address to lookup
        :param lang: accepted languages for reply
        """
        print('getgoecode of: %s' % (textaddress,))
        conn = http.client.HTTPConnection("nominatim.openstreetmap.org")
        params = urllib.parse.urlencode({
            'q': textaddress,
            'countrycodes': 'il',
            'limit': str(limit), # max results
            'polygon': '0', #Output polygon outlines for items found  (deprecated, use one of the polygon_* parameters instead)
            'email': 'oren@orengampel.com',
            'accept-language': lang,
            'format': 'json'}) #TODO check what jsonv2 means

        try:
            conn.request("GET", "/search?" + params)
        except IOError as IOe:
            print("connection to server failed: " + str(IOe))

        response = conn.getresponse()
        print(response.status, response.reason)
        d1 = response.read()
        conn.close()
        return json.loads(d1.decode('utf8'))


    @staticmethod
    def addresslookup(latlng, zoom=18, lang='he,en'):
        """Return json object with address of latlng

        :param latlng: goecode of address to look for
        :param zoom: level of info - 18 is building level
        :param lang: accepted languages
        """
        print('addresslookup of: %s' % (latlng,))
        return {'address':
                    {'house_number': '22',
                     'state': 'מחוז תל אביב',
                     'suburb': 'גבעת הרצל',
                     'country_code': 'il',
                     'postcode': '64739',
                     'city': 'תל אביב-יפו',
                     'road': 'רבנו חננאל',
                     'country': 'ישראל'},
                'display_name': '22, רבנו חננאל, גבעת הרצל, תל אביב-יפו, מחוז תל אביב, 64739, ישראל',
                'place_id': '3672610890',
                'osm_type': 'node',
                'osm_id': '2079016475',
                'lat': '32.053237',
                'lon': '34.768979'}
        # conn = http.client.HTTPConnection("nominatim.openstreetmap.org")
        # params = urllib.parse.urlencode({
        #     'lat': latlng[0], 'lon': latlng[1],
        #     'zoom': str(zoom), 'email': 'oren@orengampel.com',
        #     'accept-language': lang,
        #     'format': 'json'})
        #
        # try:
        #     conn.request("GET", "/reverse?" + params)
        # except IOError as IOe:
        #     print("connection to server failed: " + str(IOe))
        #
        # response = conn.getresponse()
        # print(response.status, response.reason)
        # d1 = response.read()
        # conn.close()
        # return json.loads(d1.decode('utf8'))


# Run a demo
if __name__ == '__main__':
    print("DEMO!!\n" + "-" * 6)
    print("driving, cycling and walking from Tel Aviv Port to Azrieli Center\n")
    route = Router(('32.07473', '34.79153'), ('32.09550', '34.77225'), 'motorcar')
    print("on car: distance: %s time: %im" % (route.getDistance(), route.getTravelTimeMin()))
    route = Router(('32.07473', '34.79153'), ('32.09550', '34.77225'), 'bicycle')
    print("on bicycle: distance: %s time: %im" % (route.getDistance(), route.getTravelTimeMin()))
    route = Router(('32.07473', '34.79153'), ('32.09550', '34.77225'), 'foot')
    print("on foot: distance: %s time: %im" % (route.getDistance(), route.getTravelTimeMin()))

    from pprint import pprint
    pprint(Router.addresslookup(('32.07473', '34.79153'), 18, 'en'))
    pprint(Router.addresslookup(('32.09550', '34.77225'), 18, 'en'))
    pprint(Router.addresslookup(('34.0174', '28.6249'), 18, 'en'))

    addrs = ["נמל, תל אביב", "ביצרון 38 תל אביב", "כיכר השעון יפו"]
    for addr in addrs:
        print("\n"+"where is: %s\n============" % (addr,))
        pprint(Router.getgoecode(addr, 1))
