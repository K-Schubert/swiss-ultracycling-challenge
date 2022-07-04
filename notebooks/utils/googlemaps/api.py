import requests
import ast

def gm_distance_api(origins, destinations, API_KEY):
    
    output_format = 'json'

    avoid = 'highways|ferries'
    mode = 'bicycling'

    origins = str(origins[0]) + '%2C' + str(origins[1])
    if len(destinations) > 1:
        destinations = "".join([str(x[0]) + '%2C' + str(x[1]) + '%7C' for x in destinations])[:-3]
    else:
        destinations = str(destinations[0][0]) + '%2C' + str(destinations[0][1])

    url = f'https://maps.googleapis.com/maps/api/distancematrix/{output_format}?&avoid={avoid}&mode={mode}&destinations={destinations}&origins={origins}&key={API_KEY["API_KEY"]}'

    if len(url) > 2000:
        raise ValueError('URL TOO LONG')
    
    resp = requests.get(url)
    data = ast.literal_eval(resp.content.decode('utf-8'))
    
    distance = [x['distance']['value'] if x['status']=='OK' else x['status'] for x in data['rows'][0]['elements']]
    time = [x['duration']['value'] if x['status']=='OK' else x['status'] for x in data['rows'][0]['elements']]
    
    return {'origin_addresses': data['origin_addresses'],
            'destination_addresses': data['destination_addresses'],
            'distance': distance,
            'time': time}

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]