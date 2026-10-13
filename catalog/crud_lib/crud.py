"""
to use from another folder use this --> "from catalog.crud_lib.crud import *"
"""

import pymongo 
from pymongo import MongoClient

cluster = MongoClient("mongodb+srv://catalog_admin:ayZh53bCpNh3gm79@catalogproject.bood3tm.mongodb.net/?retryWrites=true&w=majority")
# connection string for mongodb compass catalogProject

db = cluster["catalog_project"]
# path to Courses db in catalogProject



# GENERIC OPERATION

def crud_operation(dict_, operation_, collection_, update_operator_ = "", db_="catalog_project"):

    db = cluster[db_]
    # dynamicly supports different db, default is catalog_project

    collection = db[collection_]
    # dynamicly supports different collections

    operation_ = operation_.lower()
    # supports upper or lower case operation_ inputs

    if operation_ == "create":

        return collection.insert_one(dict_)

    elif operation_ == "return":
        
        return collection.find_one(dict_)

    elif operation_ == "update":

        return collection.update_one(dict_, update_operator_)

    elif operation_ == "delete":

        return collection.delete_one(dict_)

    elif operation_ == "create_many": # untested
        
        return collection.insert_many(dict_)

    elif operation_ == "return_update": # untested
        
        return collection.find_one_and_update(dict_, update_operator_)

    elif operation_ == "update_many": # untested

        return collection.update_many(dict_, update_operator_)

    elif operation_ == "delete": # untested

        return collection.delete_many(dict_)

    else:

        return False



# CREATE

def create_course(dict_):

    collection = db["courses"]

    return collection.insert_one(dict_)


def create_progrm(dict_):

    collection = db["program"]

    return collection.insert_one(dict_)


def create_static_text(dict_):

    collection = db["static_text"]

    return collection.insert_one(dict_)


def create_user(dict_):

    collection = db["user"]

    return collection.insert_one(dict_)



# RETURN

def return_course(dict_):

    collection = db["courses"]

    return collection.find_one(dict_)


def return_program(dict_):

    collection = db["program"]

    return collection.find_one(dict_)


def return_static_text(dict_):

    collection = db["static_text"]

    return collection.find_one(dict_)


def return_user(dict_):

    collection = db["user"]

    return collection.find_one(dict_)



# UPDATE


def update_course(dict_, update_operator_):

    collection = db["courses"]

    return collection.update_one(dict_, update_operator_)


def update_program(dict_, update_operator_):

    collection = db["program"]

    return collection.update_one(dict_, update_operator_)


def update_static_text(dict_, update_operator_):

    collection = db["static_text"]

    return collection.update_one(dict_, update_operator_)


def update_user(dict_, update_operator_):

    collection = db["user"]

    return collection.update_one(dict_, update_operator_)



# DELETE

def delete_course(dict_):

    collection = db["courses"]

    return collection.delete_one(dict_)


def delete_program(dict_):

    collection = db["program"]

    return collection.delete_one(dict_)


def delete_static_text(dict_):

    collection = db["static_text"]

    return collection.delete_one(dict_)


def delete_user(dict_):

    collection = db["user"]

    return collection.delete_one(dict_)