def getRouteReport(df_tour, df_transport, avg_speed, reverse=False):

    # sometimes tour is reversed by solver, un-reverse it
    if reverse:
        df_tour = df_tour.iloc[::-1]
        
    df_tour_eta = df_tour.copy()
    
    # compute slices of 2 for each 2 consecutive points in route
    n = 2  # group size
    m = 1  # overlap size
    l = list(df_tour.index)
    tour_slices = [l[i:i+n] for i in range(0, len(l), n-m)][:-1]

    # compute dist between two points in route
    dist = []
    for ind in tour_slices:

        dist.append(df_transport.iloc[ind[0], ind[1]])

    # transform to km
    dist = [x/1000 for x in dist]
    df_tour_eta['dist_km'] = np.insert(dist, 0, 0)
    
    # compute cum dist
    cum_dist = np.cumsum((dist))
    df_tour_eta['cum_dist_km'] = np.insert(cum_dist, 0, 0)
    
    # compute time between two points
    df_tour_eta['time_h'] = np.insert([x/avg_speed for x in dist], 0, 0)
    
    # compute elapsed time for given avg speed
    elapsed_time = np.cumsum([x/avg_speed for x in dist])
    df_tour_eta['elapsed_time_h'] = np.insert(elapsed_time, 0, 0)
    
    # define start datetime
    start_time = datetime.datetime.strptime('7/9/2022 10:10', '%d/%m/%Y %H:%M')

    # compute eta at cp
    eta_timestamp_dt = [(start_time + datetime.timedelta(hours=t)) for t in elapsed_time]
    df_tour_eta['eta'] = np.insert(eta_timestamp_dt, 0, start_time)
    
    # compute elapsed time in human readable format
    df_tour_eta['elapsed_time_hrf'] = df_tour_eta.eta.diff().fillna(pd.Timedelta(seconds=0)).cumsum()
  
    # get name of towns (non-mandatory cp)
    checkpoints_r = {v: k for k,v in checkpoints.items()}
    df_tour_eta['cp'] = [checkpoints_r[(lat, lon)] for lat, lon in zip(df_tour_eta['latitude'], df_tour_eta['longitude'])]
    
    # get opening hours for transportation at cps
    mc = {v: k for k, v in mandatory_checkpoints.items()}
    opening_hours = [cp_opening_times[mc[(lat, lon)]] if (lat, lon) in list(mc.keys()) else np.nan for lat, lon in zip(df_tour_eta['latitude'], df_tour_eta['longitude'])]
    df_tour_eta['opening_hours'] = opening_hours

    # infer if transportation at cp is open
    df_tour_eta['transport'] = ['Y' if (oh is not np.nan) and ((oh[0] < ts < oh[1]) or (oh[2] < ts < oh[3])) else np.nan for ts, oh in zip(df_tour_eta['eta'], df_tour_eta['opening_hours'])]

    return df_tour_eta