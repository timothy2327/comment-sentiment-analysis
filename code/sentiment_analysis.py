#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep 17 21:23:17 2019

@author: liudiwei
"""
import time
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer,TfidfVectorizer
from preprocessing import TextPreprocessor
import pickle
from sklearn.model_selection import train_test_split
from stacking import StackingClassifier,SubClassifier

import os
path_prefix= os.path.abspath(os.path.join(os.getcwd(), "../.."))
print(path_prefix)

def load_dataset(datapath):
    data = pd.read_csv(datapath, lineterminator="\n")
    print(data.shape)
    print(data.groupby('label').size().reset_index(name='counts'))
    return data

def build_trainset(feature_type="bow"):
    process = TextPreprocessor(stopword_file=path_prefix + "data/stopwords/stopword_normal.txt")
    train_data = load_dataset(path_prefix + "data/comment_trainset_2class.csv")#.sample(frac=0.02)
    # train_data.to_csv("data/train_data_bak.csv", index=None,encoding="UTF-8")
    train_data["label"] = train_data.label 

    X = train_data.CONTENT
    y = np.array(train_data.label.tolist())

    if feature_type == "bow":
        transformer = CountVectorizer(analyzer=process.process_line)

    elif feature_type == "word-tfidf":
        transformer = TfidfVectorizer(analyzer=process.process_line, max_features=50000)

    elif feature_type == "word-ngram-tfidf":
        transformer = TfidfVectorizer(analyzer=process.process_line, 
                                    ngram_range=(1,3))
                                    
    elif feature_type == "char-ngram-tfidf":
        transformer = TfidfVectorizer(analyzer='char', 
                                    max_features=200000,
                                    ngram_range=(2,4))#,
                                    #preprocessor=process.filter_trim)

    transformer.fit(X)
    X = transformer.transform(X)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=11)
    # X_train = np.around(X_train, decimals=4)
    # X_test = np.around(X_test, decimals=4)

    return X_train, X_test, y_train, y_test, transformer

def build_word2vec():
    """
    待完成
    """
    process = TextPreprocessor(stopword_file=path_prefix + "data/stopwords/stopword_normal.txt")
    train_data = load_dataset(path_prefix + "data/comment_trainset_2class.csv")#.sample(frac=0.02)
    # train_data.to_csv("data/train_data_bak.csv", index=None,encoding="UTF-8")
    train_data["label"] = train_data.label 

    X = train_data.CONTENT.apply(lambda x: process.process_line(x))
    y = np.array(train_data.label.tolist())
    return X, y


def data2file(data, outfile):
    if type(data) == list:
        np.savetxt(outfile, np.array(data), fmt='%f',delimiter=',')
    elif type(data) == np.ndarray:
        np.savetxt(outfile, data,fmt='%f', delimiter=',')

def loadfile(filename, delimiter=','):
    return np.loadtxt(filename, delimiter=delimiter)


def load_object(transformer_path):
    return pickle.load(open(transformer_path, "rb"))

def dump_object(obj_data, outpath):
    with open(outpath, 'wb') as fw:
        pickle.dump(obj_data, fw)

def run_sub_model():
    start = time.time()
    feature_type = "char-ngram-tfidf"
    X_train, X_test, y_train, y_test, transformer = build_trainset(feature_type=feature_type)
    print("X_train: {}, X_test: {}".format(X_train.shape, X_test.shape))
    import pickle
    transformer_path = path_prefix + 'output/{}_transformer.pkl'.format(feature_type)
    dump_object(transformer, transformer_path)

    from stacking import StackingClassifier
    sub_obj = SubClassifier()

    modellist = ["lr", "MNB"]

    for modelname in modellist:
        classifier = sub_obj.SelectModel(modelname=modelname)
        classifier.fit(X_train, y_train)
        preds = classifier.predict(X_test)

        pred_proba = classifier.predict(X_test)
        data2file(pred_proba, path_prefix + "output/{}_proba.txt".format(modelname + feature_type))
        sub_obj.performance(y_test, preds, modelname=modelname)

        stacking_obj_path = path_prefix + "output/stacking_obj_{}.pkl".format(modelname + feature_type)
        dump_object(sub_obj, stacking_obj_path)

        # 加载transformer
        bow_transformer = load_object(transformer_path)

        #测试用transform，表示测试数据，为list
        valid_data = load_dataset(path_prefix + "data/comment_testset_2class.csv")#.sample(frac=0.01)
        X_valid = bow_transformer.transform(valid_data.CONTENT)
        y_valid = np.array(valid_data.label.tolist())

        print(X_valid.shape)

        # stacking_obj = load_object(stacking_obj_path)
        preds = classifier.predict(X_valid)
        pred_proba = classifier.predict_proba(X_valid)
        sub_obj.performance(y_valid, preds, modelname=modelname)
        data2file(pred_proba, path_prefix + "./output/validset_{}_proba.txt".format(modelname + feature_type))

        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score(y_valid, pred_proba[:,1])
        print("model {a} auc score: {b}".format(a=modelname, b=auc))

        elapsed = (time.time() - start)
        print("Time used:",elapsed)

def run_stacking():
    start = time.time()
    feature_type = "char-ngram-tfidf"
    # 导入数据集切割训练与测试数据
    X_train, X_test, y_train, y_test, transformer = build_trainset(feature_type=feature_type)
    print("X_train: {}, X_test: {}".format(X_train.shape, X_test.shape))

    #测试用transform，表示测试数据，为list
    valid_data = load_dataset(path_prefix + "data/comment_testset_2class.csv")#.sample(frac=0.01)
    X_test = transformer.transform(valid_data.CONTENT)
    y_test = np.array(valid_data.label.tolist())

    import pickle
    print("save feature transformer.")
    transformer_path = path_prefix + 'output/{}_transformer.pkl'.format(feature_type)
    dump_object(transformer, transformer_path)

    #layer 1：多模型融合
    classifiers = {
            'lr': SubClassifier().SelectModel(modelname="lr"),
            'rf': SubClassifier().SelectModel(modelname="RF"),
            'mnb':  SubClassifier().SelectModel(modelname="MNB")
        }
    
    meta_classifier = SubClassifier().SelectModel(modelname="xgboost")

    stacking_clf = StackingClassifier(classifiers, meta_classifier, n_classes=2, n_folds=5)

    stacking_clf.fit(X_train, y_train)
    pred = stacking_clf.predict(X_test)
    pred_proba = stacking_clf.predict_prob(X_test)

    #模型评估
    stacking_clf.performance(y_test, pred)
    # 96.4228934817

    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(y_test, pred_proba[:,1])
    print("model auc score: {b}".format(b=auc))

    elapsed = (time.time() - start)
    print("Time used:",elapsed)

if  __name__ == "__main__":
    run_stacking()