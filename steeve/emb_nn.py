from __future__ import division
import pandas as pd
import numpy as np


# In[2]:

import gc
import subprocess
from sklearn.model_selection import KFold
import lightgbm as lgb
import os
import pickle
from keras.models import Model
from keras.layers import Dense, Dropout, Input
from keras.optimizers import Adam
from sklearn.model_selection import KFold
import tensorflow as tf
from keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau
from keras.backend.tensorflow_backend import set_session
from keras.preprocessing.sequence import pad_sequences
from keras.layers import Input, Dropout, Dense, concatenate, CuDNNGRU, Embedding, Flatten, Activation, BatchNormalization, PReLU
from keras.initializers import he_uniform, RandomNormal
from keras.layers import Conv1D, SpatialDropout1D, Bidirectional, Reshape
from keras.layers import GlobalMaxPooling1D, GlobalAveragePooling1D
from sklearn.model_selection import KFold
from tqdm import tqdm
from nltk import ngrams
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error

os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL']='2'

# restrict gpu usage
config = tf.ConfigProto()
config.gpu_options.allow_growth = True
sess = tf.Session(config=config)
set_session(sess)

# test = pd.read_csv('../input/test.csv.zip', parse_dates=["activation_date"])
# train = pd.read_csv('../input/train.csv.zip', parse_dates=["activation_date"])

with open('../input/train_ridge.p', 'rb') as f:
    train = pickle.load(f)
    
with open('../input/test_ridge.p', 'rb') as f:
    test = pickle.load(f)    
# print(train.columns)    
# with open('../input/inception_v3_include_head_max_train.p','rb') as f:
#     x = pickle.load(f)
    
# train_features = x['features']
# train_ids = x['ids']

# with open('../input/inception_v3_include_head_max_test.p','rb') as f:
#     x = pickle.load(f)

# test_features = x['features']
# test_ids = x['ids']    

# del x
# gc.collect()



# incep_train_image_df = pd.DataFrame(train_features, columns = ['image_quality'])
# incep_test_image_df = pd.DataFrame(test_features, columns = [f'image_quality'])
# incep_train_image_df['image'] = train_ids
# incep_test_image_df['image'] = test_ids
# train = train.join(incep_train_image_df.set_index('image'), on='image')
# test = test.join(incep_test_image_df.set_index('image'), on='image')    

data = pd.concat([train, test], axis=0)

text_col = ['title', 'description', 'param_1', 'param_2', 'param_3']
for c in text_col:
    data[c].fillna(f'No {c}', inplace=True)

# data['text_feat'] = data.apply(lambda row: ' '.join([
#     str(row['param_1']), 
#     str(row['param_2']), 
#     str(row['param_3'])]),axis=1) # Group Param Features

    
#fill mean for price    
# data['price'].fillna(data.loc[~data.price.isna()].mean(), inplace=True)
# mean_image_quality = data.loc[~data.image_quality.isna(), 'image_quality'].mean()
# data['image_quality'].fillna(mean_image_quality, inplace=True)
# print(mean_image_quality, flush=True)
data['item_seq_number'] = np.log1p(data['item_seq_number']).astype(np.float32)
data['price'] = np.log1p(data['price']).astype(np.float32)
data['des_len'] = data.description.str.len()
data['des_nwords'] = data.description.str.split().apply(len)  
# data['text_feat_len'] = data.text_feat.str.len()
# data['text_feat_nwords'] = data.text_feat.str.split().apply(len)  
# data['title_len'] = data.title.str.len()
# data['title_nwords'] = data.title.str.split().apply(len)

cont_features = ['price']
cont_features.append('des_len')
cont_features.append('des_nwords')
cont_features.append('item_seq_number')
cont_features.append('ridge_feature')
# cont_features.append('text_feat_len')
# cont_features.append('text_feat_nwords')

# cont_features.append('title_len')
# cont_features.append('title_nwords')

agg_cols = ['param_1']

# for c in tqdm(agg_cols):
#     gp = train.groupby(c)['deal_probability']
#     mean = gp.mean()
#     std  = gp.std()
#     data[c + '_deal_probability_avg'] = data[c].map(mean)
#     cont_features.append(c + '_deal_probability_avg')    
#     data[c + '_deal_probability_std'] = data[c].map(std)

#     cont_features.append(c + '_deal_probability_std')
    
cate_cols = ['city',  'category_name', 'user_type','parent_category_name','region','param_1','param_2','param_3', 'image_top_1']

for c in tqdm(cate_cols):    
    data[c] = LabelEncoder().fit_transform(data[c].values.astype('str'))    

    

new_data = data.drop(['user_id','description','image',
                      'item_id','title'], axis=1)
new_data.fillna(0, inplace= True)

X = new_data.loc[new_data.activation_date<=pd.to_datetime('2017-04-07')]
X_te = new_data.loc[new_data.activation_date>=pd.to_datetime('2017-04-08')]
print(f'cont_features: {cont_features}', flush=True)
print(f'columns: {new_data.columns}', flush=True)
# the word must appear at least five time        


with open(f'../input/train_des_seq.p','rb') as f:
    train_des_seq = pickle.load(f)
    
with open(f'../input/test_des_seq.p','rb') as f:
    test_des_seq = pickle.load(f)
    
with open(f'../input/train_title_seq.p','rb') as f:
    train_title_seq = pickle.load(f)    

with open(f'../input/test_title_seq.p','rb') as f:
    test_title_seq = pickle.load(f)    
    
# with open('../input/train_des_vec_word_swr_lower_rmspecial_10000.p','rb') as f:
#     train_des_vec = pickle.load(f)    

# with open('../input/test_des_vec_word_swr_lower_rmspecial_10000.p','rb') as f:
#     test_des_vec = pickle.load(f)        


with open(f'../input/word_index.p','rb') as f:
    word_index = pickle.load(f)    

max_text = len(word_index)+1
with open(f'../input/embedding_matrix_pk.p', 'rb') as f:
    embedding_matrix =  pickle.load(f)       


def get_keras_fasttext(df, des_seq, title_seq):
    X = {
        'description': des_seq,
        'title': title_seq,

        'user_type': np.array(df['user_type']),
        'parent_category_name': np.array(df['parent_category_name']),        
        'category_name': np.array(df['category_name']),
        'param_1': np.array(df['param_1']),
        'param_2': np.array(df['param_2']),
        'param_3': np.array(df['param_3']),
        'region': np.array(df['region']),
        'city': np.array(df['city']),
        'image_top_1': np.array(df['image_top_1']),
        'ridge_feature':np.array(df['ridge_feature']),
#         'description_vector':des_vec,
#         'price': np.array(df['price']),
#         'image_top_1_deal_probability_avg': np.array(df['image_top_1_deal_probability_avg']),
#         'image_top_1_deal_probability_std': np.array(df['image_top_1_deal_probability_std']),
#         'item_seq_number_deal_probability_avg': np.array(df['item_seq_number_deal_probability_avg']),
#         'item_seq_number_deal_probability_std': np.array(df['item_seq_number_deal_probability_std']),   

#         'cont_features':np.reshape([df['price'].values]  \
#                                        +[ df[c+ '_deal_probability_avg'].values for c in agg_cols]\
#                                       +[ df[c+ '_deal_probability_std'].values for c in agg_cols], (len(df), -1) )
    }
    for feat in cont_features:
        X[feat] = np.array(df[feat])
    return X

max_des_len = 80
max_title_len = 30


max_user_type= np.max(new_data['user_type'].max()) + 1
max_parent_category_name= np.max(new_data['parent_category_name'].max()) + 1
max_category_name= np.max(new_data['category_name'].max()) + 1
max_param_1 = np.max(new_data['param_1'].max()) + 1
max_param_2 = np.max(new_data['param_2'].max()) + 1
max_param_3 = np.max(new_data['param_3'].max()) + 1
max_region = np.max(new_data['region'].max()) + 1
max_city = np.max(new_data['city'].max()) + 1
max_image_top_1 = np.max(new_data['image_top_1'].max()) + 1

del data, new_data
gc.collect()
y_train = X['deal_probability']
X = X.drop(['deal_probability','activation_date'],axis=1)
X_te = X_te.drop(['deal_probability','activation_date'],axis=1)

x_train = get_keras_fasttext(X, train_des_seq, train_title_seq)
x_test = get_keras_fasttext(X_te, test_des_seq, test_title_seq)
# print(f"cont size: {x_train['cont_features'].shape}")    

hyper_params={
    'description_embedding': 32, 
    'title_embedding': 16, 
    'category_name_embedding': 4,
    'parent_category_name_embedding': 4, 
    'param_1_embedding': 8, 
    'param_2_embedding': 8, 
    'param_3_embedding': 32, 
    'city_embedding': 16, 
    'region_embedding': 32, 
    'image_top_1_embedding': 64, 
    'user_type_embedding': 2
}
print(hyper_params, flush=True)
def gauss_init():
    return RandomNormal(mean=0.0, stddev=0.005)

def get_vanilla_model():
    description = Input(shape=[x_train["description"].shape[1]], name="description")
    title = Input(shape=[x_train["title"].shape[1]], name="title")
    user_type = Input(shape=[1], name="user_type")
    category_name = Input(shape=[1], name="category_name")
    parent_category_name = Input(shape=[1], name="parent_category_name")    
    param_1 = Input(shape=[1], name="param_1")
    param_2 = Input(shape=[1], name="param_2")
    param_3 = Input(shape=[1], name="param_3")
    region = Input(shape=[1], name="region")
    city = Input(shape=[1], name="city")
    image_top_1 = Input(shape=[1], name="image_top_1")
#     description_vector = Input(shape=[x_train["description_vector"].shape[1]], name="description_vector", sparse=True)
#     des_vec = Dense(100)(description_vector)
#     price = Input(shape=[1], name="price")
#     image_top_1_deal_probability_avg = Input(shape=[1], name="image_top_1_deal_probability_avg")
#     image_top_1_deal_probability_std = Input(shape=[1], name="image_top_1_deal_probability_std")

#     item_seq_number_deal_probability_avg = Input(shape=[1], name="item_seq_number_deal_probability_avg")
#     item_seq_number_deal_probability_std = Input(shape=[1], name="item_seq_number_deal_probability_std")
#     des_len = Input(shape=[1], name="des_len")
#     des_nwords = Input(shape=[1], name="des_nwords")
    
    continuous_inputs = [Input(shape=[1], name=feat) for feat in cont_features]
#     continuous_features = concatenate(continuous_inputs, axis=1)
#     continuous_features = Reshape([1,len(cont_features)])(continuous_features)
#     cont_x = CuDNNGRU(20)(continuous_features)
#     shared_embedding = Embedding(max_text, 300, weights=[embedding_matrix], trainable=True)        
#     shared_embedding = Embedding(max_text, hyper_params['description_embedding'], embeddings_initializer = gauss_init())    
    desc_embedding = Embedding(max_text, hyper_params['description_embedding'], embeddings_initializer = gauss_init())    
    title_embedding = Embedding(max_text, hyper_params['title_embedding'], embeddings_initializer = gauss_init())        
    emb_description = desc_embedding (description)
#     emb_description = shared_embedding (description)    
#     emb_description = SpatialDropout1D(0.2)(emb_description)
#     emb_description = CuDNNGRU(50, return_sequences=True)(emb_description)
#     emb_description = Conv1D(filters=hyper_params['description_filters'], kernel_size=3, activation='relu')(emb_description)

    emb_title = title_embedding (title)
#     emb_title = shared_embedding (title)
#     emb_title = Conv1D(filters=hyper_params['title_filters'], kernel_size=3, activation='relu')(emb_title)
    
    
    emb_user_type = Flatten() ( Embedding(max_user_type, hyper_params['user_type_embedding'], embeddings_initializer = gauss_init())(user_type)    )
    emb_param_1 = Flatten() ( Embedding(max_param_1, hyper_params['param_1_embedding'], embeddings_initializer = gauss_init())(param_1) )
    emb_param_2 = Flatten() ( Embedding(max_param_2, hyper_params['param_2_embedding'], embeddings_initializer = gauss_init())(param_2) )
    emb_param_3 = Flatten() ( Embedding(max_param_3, hyper_params['param_3_embedding'], embeddings_initializer = gauss_init())(param_3) )
    emb_category_name =  Flatten() ( Embedding(max_category_name, hyper_params['category_name_embedding'], embeddings_initializer = gauss_init())(category_name) )
    emb_parent_category_name =  Flatten() ( Embedding(max_parent_category_name, hyper_params['parent_category_name_embedding'], embeddings_initializer = gauss_init())(parent_category_name) )
    emb_region = Flatten() ( Embedding(max_region, hyper_params['region_embedding'], embeddings_initializer = gauss_init())(region) )
    emb_city = Flatten() ( Embedding(max_city, hyper_params['city_embedding'], embeddings_initializer = gauss_init())(city) )
    emb_image_top_1 = Flatten() ( Embedding(max_image_top_1, hyper_params['image_top_1_embedding'], embeddings_initializer = gauss_init())(image_top_1) )
    
    emb_description = GlobalMaxPooling1D( name='output_des_max' )(emb_description)
    emb_title = GlobalMaxPooling1D(name='output_title_max' )(emb_title)

    x = concatenate([ emb_description, emb_title, emb_region, emb_city, emb_category_name, emb_parent_category_name,
    emb_user_type, emb_param_1, emb_param_2, emb_param_3, emb_image_top_1, *continuous_inputs] )
    x = BatchNormalization()(x)
    
    x = Dense(1024)(x)
    x = Activation('relu')(x)
    
    x = Dense(1, activation="sigmoid") (x)
    model = Model([description, title,  user_type , category_name, parent_category_name, param_1, param_2, param_3,
                   region,city, image_top_1, *continuous_inputs] ,
                   x)
    optimizer = Adam(.002, amsgrad=True)
    model.compile(loss="mse", optimizer=optimizer)
    return model



def train_bagging(X, y, fold_count):
    
    
    kf = KFold(n_splits=fold_count, random_state=42, shuffle=True)
#     skf = StratifiedKFold(n_splits=fold_count, random_state=None, shuffle=False)
    fold_id = -1
#     model_list = []
    val_predict= np.zeros(y.shape)
#     rmse_list = []
    for train_index, test_index in kf.split(X['city']):
        
        fold_id +=1 
        
#         if fold_id !=0: continue
        print(f'fold number: {fold_id}', flush=True)
        
        
#         x_train, x_val = X[train_index], X[test_index]
        x_train = {}
        x_val = {}
        for key in X:
#             print(key, X[key][train_index].shape)
            x_train[key] = X[key][train_index]
            x_val[key] = X[key][test_index]
        y_train, y_val = y[train_index], y[test_index]

        model_path = f'../weights/{fname}_fold{fold_id}.hdf5'
        #if model weights exist
        if os.path.exists(model_path):
            print('weight loaded')
            model = get_model()
            model.load_weights(model_path)
            y_pred = model.predict(x_val)        
            val_predict[test_index] = y_pred[:,0]
#             model_list.append(model)
            rmse = mean_squared_error(y_val, y_pred) ** 0.5
            del model
            gc.collect()
            print(f'rmse: {rmse}')
            rmse_list.append(rmse)
            continue
        
        model = get_model()

        early= EarlyStopping(monitor='val_loss', patience=4, verbose=0, mode='auto')
        checkpoint = ModelCheckpoint(model_path, monitor='val_loss', verbose=1, save_best_only=True, mode='auto')
        rlrop = ReduceLROnPlateau(monitor='val_loss',mode='auto',patience=2,verbose=1,factor=0.1,cooldown=0,min_lr=1e-6)
        callbacks = [early, checkpoint, rlrop]
        
        model.fit(x_train, y_train, validation_data=(x_val, y_val), callbacks=callbacks, epochs=epochs, verbose=0)
        model.load_weights(model_path)
        y_pred = model.predict(x_val)        
        val_predict[test_index] = y_pred[:,0]
        rmse = mean_squared_error(y_val, y_pred) ** 0.5
        print(f'rmse: {rmse}')
        del model
        gc.collect()
        rmse_list.append(rmse)
#         model_list.append(model)
    print(f'rmse score avg: {np.mean(rmse_list)}', flush=True)
    return val_predict




# In[57]:


# weight_dir = '../weights/'
epochs = 10
batch_size = 1024
nfold = 5
rmse_list = []

fname = 'mercari_no2_sol_split_16_32_emb_price_ridge_deslen_hpt1_nn_5fold'
# fname = 'mercari_no2_sol_emb_bigru_60_5fold'
# fname = 'mercari_no2_sol_emb_cnn_f12_5fold'

# get_model = get_cnn_model
# get_model = get_gru_model
get_model = get_vanilla_model

print(get_model().summary(), flush=True)
print(f'fname {fname}', flush=True)

val_predict = train_bagging(x_train, y_train, nfold)
# print(f"model list length: {len(model_list)}")

# fname = 'des_word_svd_200_char_svd_1000_title_200_resnet50_500_lgb_1fold'
model = get_model()

print('storing test prediction', flush=True)
for index in tqdm(range(nfold)):
    model_path = f'../weights/{fname}_fold{index}.hdf5'
    model.load_weights(model_path)
    if index == 0: 
        y_pred = model.predict(x_test)
    else:
        y_pred *= model.predict(x_test)
#         y_pred += model.predict(x_test)
    
y_pred = np.clip(y_pred, 0, 1)
y_pred = y_pred **( 1.0/ (nfold))
# y_pred /= nfold

print('storing test prediction', flush=True)
sub = pd.read_csv('../input/sample_submission.csv')
sub['deal_probability'] = y_pred
sub['deal_probability'].clip(0.0, 1.0, inplace=True)
sub.to_csv(f'../output/{fname}_test.csv', index=False)


print('storing oof prediction', flush=True)
train_data = pd.read_csv('../input/train.csv.zip')
label = ['deal_probability']
train_user_ids = train_data.user_id.values
train_item_ids = train_data.item_id.values

train_item_ids = train_item_ids.reshape(len(train_item_ids), 1)
train_user_ids = train_item_ids.reshape(len(train_user_ids), 1)

val_predicts = pd.DataFrame(data=val_predict, columns= label)
val_predicts['user_id'] = train_user_ids
val_predicts['item_id'] = train_item_ids
val_predicts.to_csv(f'../output/{fname}_train.csv', index=False)
# submit via kaggle api
# cmd = f'kaggle competitions submit -c avito-demand-prediction -f ../output/{fname}_test.csv -m "cv:{np.mean(rmse_list)}"'
# subprocess.call(cmd.split())