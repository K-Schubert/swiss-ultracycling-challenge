import os
import pandas as pd
import numpy as np
import ast

from dotenv import load_dotenv

from utils.gpsconversion.conversionapi import convertWSG84toMN95

load_dotenv()

DATA_PATH = os.environ['DATA_PATH']

def createDistanceMatrix(api_data):

    df = pd.DataFrame(np.zeros((len(api_data.keys()), len(api_data.keys()))))

    for i, (key, val) in enumerate(api_data.items()):

        df.loc[i, i] = 999999
        df.loc[i, np.where(df.loc[i]!=999999)[0]] = val


    df.replace({'ZERO_RESULTS': 999999}, inplace=True)

    # GM TRANSPORT CORRECTIONS
    ###########################################################################
    
    # ST IMIER
    df.loc[0, 1] = 320
    df.loc[1, 0] = 300

    # LENZERHEIDE TGANTIENI-LIFT
    df.loc[2, 3] = 240
    df.loc[3, 2] = 300

    # LENZERHEIDE TGANTIENI-SPORZ
    df.loc[2, 4] = 90
    df.loc[4, 2] = 500

    # LENZERHEIDE LIFT-SPORZ
    df.loc[3, 4] = 480
    df.loc[4, 3] = 120

    # LENZERHEIDE BECKENRIED-GERSAU
    df.loc[5, 6] = 1200
    df.loc[6, 5] = 1200

    # LENZERHEIDE GOSCHENEN-AIROLO
    df.loc[7, 29] = 900
    df.loc[29, 7] = 4500

    # LENZERHEIDE SANETSCH-GSTEIG
    df.loc[8, 32] = 900
    df.loc[32, 8] = 16200

    return df

def createDummyNode(df, start, end, checkpoints):

    df[len(df)] = 999999
    df.loc[len(df)] = 999999

    ind_start = [x==start for x in checkpoints.keys()]
    ind_start = np.where(ind_start)[0][0]

    ind_end = [x==end for x in checkpoints.keys()]
    ind_end = np.where(ind_end)[0][0]

    # 0 for dummy-dummy
    df.loc[len(df)-1, len(df)-1] = 0

    # 0 for start-end and end-start
    df.loc[ind_start, len(df)-1] = 0
    df.loc[ind_end, len(df)-1] = 0
    df.loc[len(df)-1, ind_start] = 0
    df.loc[len(df)-1, ind_end] = 0

    df = df.astype('int')

    return df

def createClusters(checkpoints, cluster_mapping):

    such_2022 = pd.DataFrame([x for x in checkpoints.values()])
    
    # DUMMY NODE
    such_2022 = such_2022.append([(45, 6.9)])

    such_2022['cluster'] = ['BE1', 'BE2', 'GR1', 'GR2', 'GR3', 'NW', 'SZ', 'UR', 'VS', 'GE', 'VD', 'NE', 'NE', 'NE', 'JU', 'BL', 'SO', 'BS', 'AG', 'ZH', 'TG', 'SG', 'AR', 'AI', 'GL', 'ZG', 'LU', 'LU', 'OW', 'TI', 'SH', 'FR', 'BE', 'FR', 'FR', 'TI', 'END', 'DUMMY']

    ######### LOAD CLUSTER MAPPING HERE IF USING FCT
    
    such_2022.replace(cluster_mapping, inplace=True)
    such_2022.reset_index(drop=True, inplace=True)

    clusters = such_2022.groupby(by='cluster')
    clusters = [(cluster[0], [x+1 for x in list(cluster[1].index)]) for cluster in clusters]

    return such_2022, clusters

def createGTSPfile(df, clusters):

    try:
            os.remove(os.path.join(DATA_PATH, 'GTSP_FILES', 'test_2022.gtsp'))
    except FileNotFoundError:
        pass

    dim = len(df)
    sets = len(clusters)

    # WRITE PARAMS AND WEIGHTS TO FILE
    params = f'NAME: such_test_3 \n\
    TYPE: AGTSP \n\
    COMMENT: test \n\
    DIMENSION: {dim} \n\
    GTSP_SETS: {sets} \n\
    EDGE_WEIGHT_TYPE: EXPLICIT \n\
    EDGE_WEIGHT_FORMAT: FULL_MATRIX \n\
    EDGE_WEIGHT_SECTION \n\
    {df.to_string(header=False, index=False)} \n\
    GTSP_SET_SECTION: \n'

    with open(os.path.join(DATA_PATH, 'GTSP_FILES', 'test_2022.gtsp'), 'a') as gtsp_file:
        gtsp_file.write(params)

    # WRITE SET SECTION
    outfile = open(os.path.join(DATA_PATH, 'GTSP_FILES', 'test_2022.gtsp'), 'a')

    for cluster in clusters:
        out = str(cluster[0]) + ' ' + ' '.join([str(x) for x in cluster[1]]) + ' -1' + '\n'
        outfile.write(out)

    outfile.close()

    # WRITE EOF
    with open(os.path.join(DATA_PATH, 'GTSP_FILES', 'test_2022.gtsp'), 'a') as gtsp_file:
        gtsp_file.write('EOF')

def loadOptimalTour(tour_filename):

    with open(os.path.join(DATA_PATH, 'TOUR_FILES', tour_filename)) as f:
        file = f.readlines()

    tour = ast.literal_eval(file[-1].split(": ")[-1])
    tour = [x-1 for x in tour]

    tour_cost = file[6].split(': ')[-1].strip()

    return tour, tour_cost

def reOrderTour(such_2022, tour, cluster_mapping):



    df_tour = such_2022.loc[tour].replace({v: k for k, v in cluster_mapping.items()}).iloc[::-1]

    df_1 = df_tour.loc[df_tour[df_tour.cluster == 'DUMMY'].index[0]:].iloc[1:]
    df_2 = df_tour.loc[:df_tour[df_tour.cluster == 'DUMMY'].index[0]].iloc[:-1]
    df_tour = pd.concat([df_1, df_2])

    df_tour.replace({0: 'latitude', 1: 'longitude'}, inplace=True)

    such_2022 = such_2022.rename(columns={0: 'latitude', 1: 'longitude'})

    tour_coord_x, tour_coord_y = convertWSG84toMN95(df_tour)

    return tour_coord_x, tour_coord_y




