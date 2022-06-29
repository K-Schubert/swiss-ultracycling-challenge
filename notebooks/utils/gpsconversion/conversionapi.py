import requests
import pandas as pd
import ast

def convertWSG84toMN95(df_tour):

    tour_coord_x = []
    tour_coord_y = []

    # CONVERT WSG84 (GPS) COORDS TO MN95 (BERN) VIA API
    # need to reverse df order SOMETIMES
    for i, coords in df_tour.iterrows():
    #for i, coords in such_2022.loc[tour].iterrows():

        url = f'http://geodesy.geo.admin.ch/reframe/wgs84tolv95?easting={coords.longitude}&northing={coords.latitude}&format=json'
        res = requests.get(url)
        res = ast.literal_eval(res.content.decode('utf-8'))
        tour_coord_y.append(res['northing'])
        tour_coord_x.append(res['easting'])

    tour_coord_x = [float(x) for x in tour_coord_x]
    tour_coord_y = [float(y) for y in tour_coord_y]

    return tour_coord_x, tour_coord_y