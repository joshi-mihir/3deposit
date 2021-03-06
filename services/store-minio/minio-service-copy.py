import os
import json
from json import JSONDecodeError
from flask import Flask, request, jsonify, send_file
from minio import Minio
from minio.error import ResponseError, BucketAlreadyExists, NoSuchBucket, NoSuchKey, AccessDenied
from minio.error import SignatureDoesNotMatch, InvalidBucketError, InvalidAccessKeyId, SignatureDoesNotMatch, BucketAlreadyOwnedByYou
from werkzeug.exceptions import BadRequestKeyError

# ACCESS KEY AKIAIOSFODNN7GRAINGER
# SECRET KEY wJalrXUtnFEMI/K7MDENG/bPxRfiCYGRAINGERKEY

# if sys.argv(2):
#     SERVER_ENDPOINT = 'minio-server:9000'
# else:
#     SERVER_ENDPOINT = 'localhost:9000'

SERVER_ENDPOINT = 'minio-server:9000'

#BUCKET_NAME = 'new-3deposit'


def minio_keys(request_auth):
    if not request_auth:
        return False
    
    # config = json.loads(request_auth.form.get('config'))
    # auth = config.get('auth')
    

    try:
        config = json.loads(request_auth.form.get('config'))
        auth = config.get('auth')
        auth_packed = {"access_key":auth.get('access_key'),"secret_key":auth.get('secret_key')}
        return auth_packed
    except JSONDecodeError:
        return {"err":"Invalid formatting of auth data."}
    except InvalidAccessKeyId as err:
        return {"err":str(err)}
    except AttributeError as err:
        return {"err":"Please provide auth keys. "}

def create_app():
    app = Flask(__name__)

    
    #************************************************************************************************************************************************************************
    #AT THIS ENDPOINT, EACH ACTION IS SPECIFIC TO AN OBJECT AT IT'S CORE
    #************************************************************************************************************************************************************************
    

    @app.route('/minio_object', methods=['GET', 'POST','DELETE'])
    def minio_object():

        
        ####################################################################################################################
        #Extract an object from a specified bucket
        ####################################################################################################################
  

        if request.method == 'GET':
            # get keys from request args
            if minio_keys(request):
                auth = minio_keys(request)
                if "err" in auth:
                    return jsonify(auth)
            else:
                return jsonify({"err": "No authentication keys provided"})

            try:
                minioClient = Minio(SERVER_ENDPOINT,
                                    access_key=auth.get("access_key"),
                                    secret_key=auth.get("secret_key"),
                                    secure=False)

                deposit_id = False

                if not deposit_id:
                    config = json.loads(request.form.get('config'))
                deposit_id = config.get('deposit_id')
                bucket_name = config.get('bucket_name')

                temp_obj_path = str(deposit_id)
                obj = minioClient.get_object(bucket_name, deposit_id)

                with open(temp_obj_path, 'wb') as file_data:
                    for d in obj.stream(32*1024):
                        file_data.write(d)

                return send_file(temp_obj_path, mimetype="application/octet-stream")

            except NoSuchKey as err:
                return jsonify({"err":"The requested deposit_id does not exist"})
            except NoSuchBucket as err:
                return jsonify({"err":str(err)})
            except (InvalidBucketError, TypeError, NoSuchBucket):
                return jsonify({"err":"Please provide valid bucket_name"})
            except (AccessDenied, InvalidAccessKeyId, SignatureDoesNotMatch):
                return jsonify({"err":"Invalid Authentication."})
            except JSONDecodeError as err:
                return jsonify({"err":"Incorrect formatting of data"})
            except ResponseError as err:
                return jsonify({"err": err})


        ####################################################################################################################
        #Puts one object i.e. a file in the specified bucket only.
        ####################################################################################################################
     

        elif request.method == 'POST':
            # get data from request payload
            try:
                config = json.loads(request.form.get('config'))
                data = json.loads(request.form.get('data'))
            
            
            # extract authentication details
                if minio_keys(request):
                    auth = minio_keys(request)
                    if "err" in auth:
                        return jsonify(auth)
                else:
                    return jsonify({"err": "No authentication keys provided"})

            # Initialize minioClient with an endpoint and keys.
                minioClient = Minio(SERVER_ENDPOINT,
                                access_key=auth.get("access_key"),
                                secret_key=auth.get("secret_key"),
                                secure=False)

            # extract deposit_id value
                if data.get('deposit_id'):
                    deposit_id = data.get('deposit_id')
                else:
                    return jsonify({"err":"Please provide a deposit_id"})

                # extract file & temp save to disk
                file = request.files['file']
                file.save(deposit_id)
            

                # extract bucket_name value
                bucket_name = config.get('bucket_name')
                minioClient.bucket_exists(bucket_name)
                metadata={}
                metadata['BUCKET_NAME'] = bucket_name

                r = minioClient.fput_object(bucket_name, object_name=deposit_id, file_path=deposit_id,metadata=metadata)
                # cleanup temp file
                os.remove(deposit_id)
                return jsonify({"etag": r, "deposit_id": deposit_id,"metadata":metadata})
            
            except (NoSuchBucket, InvalidBucketError) as err:
                return jsonify({"err":"This bucket does not exist. Please create this bucket at the bucket scoped endpoint."})
            except (InvalidAccessKeyId, AccessDenied, SignatureDoesNotMatch) as err:
                return jsonify({"err":"Invalid Authentication."})
            except BadRequestKeyError as err:
                return jsonify({"err":"Please attach a file to the request"})
            except JSONDecodeError:
                return jsonify({"err":"Incorrect formatting of data"})
            except ResponseError as err:
                return jsonify({"err": err})
            except TypeError as err:
                return jsonify({"err":"Please enter a bucket_name"})



        #################################################################################################################### 
        #Deletes one object i.e. a file from the specified bucket only.
        ####################################################################################################################


        elif request.method == 'DELETE':
            # extract authentication details
            if minio_keys(request):
                auth = minio_keys(request)
                if "err" in auth:
                    return jsonify(auth)
            else:
                return jsonify({"err": "No authentication keys provided"})

            # get data from request payload
            config = json.loads(request.form.get('config'))
            data = json.loads(request.form.get('data'))

            # extract bucket_name value
            bucket_name = config.get('bucket_name')

            # extract object specific deposit_id
            if data.get('deposit_id'):
                deposit_id = data.get('deposit_id')
            else:
                return jsonify({"err":"Please enter valid deposit_id."})

            try:
                minioClient = Minio(SERVER_ENDPOINT,
                                access_key=auth.get("access_key"),
                                secret_key=auth.get("secret_key"),
                                secure=False)
            except AccessDenied as err:
                return jsonify({"err": str(err)})

            try:
                error = minioClient.get_object(bucket_name, deposit_id)
                rem_object = minioClient.remove_object(bucket_name,deposit_id)
            except (NoSuchBucket, InvalidBucketError, ResponseError, TypeError):
                return jsonify({ "err": "Bucket does not exist." })
            except NoSuchKey:
                return jsonify({ "err": "Please enter valid deposit_id." })
            except (AccessDenied, InvalidAccessKeyId, SignatureDoesNotMatch) as err:
                return jsonify({"err":"Invalid Authentication."})                

            return jsonify({"deposit_id": deposit_id})

        else:
            return jsonify({"err":"Unsupported method"})






    
    #************************************************************************************************************************************************************************
    #AT THIS ENDPOINT, EACH ACTION IS SPECIFIC TO A BUCKET AT IT'S CORE
    #************************************************************************************************************************************************************************
    






    @app.route('/bucket', methods=['GET','POST'])
    def bucket():

        ###########################################################################################################################
        #Get metadata of all or a list of objects in a specific bucket
        ###########################################################################################################################

        if request.method == 'GET':
            # get keys from request args

            if minio_keys(request):
                auth = minio_keys(request)
                if "err" in auth:
                    return jsonify(auth)
            else:
                return jsonify({"err": "No authentication keys provided"})

            try:
                # Initialize minioClient with an endpoint and keys.
                try:
                    minioClient = Minio(SERVER_ENDPOINT,
                                    access_key=auth.get("access_key"),
                                    secret_key=auth.get("secret_key"),
                                    secure=False)
                except AccessDenied as err:
                    return jsonify({"err": str(err)})

                deposit_id_list = []
                # get data from request payload
                # if not request.form.get('data'):
                #     return jsonify({ "err": "No request provided."})

                try:
                    config = json.loads(request.form.get('config'))
                    try:
                        bucket_name = config.get('bucket_name')
                        deposit_id_list = config.get('deposit_id_list')
                    # except TypeError:
                    #     return jsonify({ "err": "TEST EXCEPTION 1" })
                    except Exception:
                        return jsonify({"err": "No data provided"})                 
                    # get objects from bucket
                    try:
                        objects = minioClient.list_objects(bucket_name, recursive=True)
                    except NoSuchBucket:
                        return jsonify({ "err": "Bucket does not exist." })
                    # except TypeError:
                    #     return jsonify({ "err": "TEST EXCEPTION 2" })
                except JSONDecodeError as err:
                    return jsonify({ "err": "Incorrect formatting of data field." })
                # except TypeError:
                #     return jsonify({ "err": "TEST EXCEPTION 3" })
                

                obj_names = []
                missing_ids = []
                test_ids = []

                objects_list = []

                if deposit_id_list:
                    try:
                        for obj in objects:
                            if obj.object_name not in deposit_id_list:
                                continue
                            ret_object = {"metadata": str(obj.metadata),
                                          "deposit_id": str(obj.object_name),
                                          "modified": str(obj.last_modified),
                                          "etag": str(obj.etag),
                                          "size": str(obj.size),
                                          "content_type": str(obj.content_type)}
                            objects_list.append(ret_object)

                            obj_names.append(str(obj.object_name))
                    except NoSuchBucket as err:
                        return jsonify({"err":"Bucket does not exist."})
                    except (AccessDenied, InvalidAccessKeyId, SignatureDoesNotMatch):
                        return jsonify({"err":"Invalid Authentication."})
                    except (InvalidBucketError, TypeError):
                        return jsonify({"err":"Please enter a valid bucket_name"})

                    for i,d in enumerate(deposit_id_list):
                        if d not in obj_names:
                            missing_ids.append(d)

                else:
                    try:
                        for obj in objects:
                            ret_object = {"metadata": str(obj.metadata), 
                                          "deposit_id": str(obj.object_name), 
                                          "modified": str(obj.last_modified),
                                          "etag": str(obj.etag), 
                                          "size": str(obj.size), 
                                          "content_type": str(obj.content_type)}
                            objects_list.append(ret_object)
                    except NoSuchBucket as err:
                        return jsonify({"err":"Bucket does not exist."})
                    except (AccessDenied, InvalidAccessKeyId, SignatureDoesNotMatch):
                        return jsonify({"err":"Invalid Authentication."})
                    except (InvalidBucketError, TypeError):
                        return jsonify({"err":"Please enter a valid bucket_name"})
                    #obj_names.append(str(obj.object_name))


                return jsonify({"objects": objects_list,"missing deposit ids":missing_ids})

            except ResponseError as err:
                return jsonify({"err": err})


        ###########################################################################################################################
        #Create a new bucket that does not yet exist
        ###########################################################################################################################

        elif request.method == 'POST':
            
            # extract authentication details
            if minio_keys(request):
                auth = minio_keys(request)
                if "err" in auth:
                    return jsonify(auth)
            else:
                return jsonify({"err": "No authentication keys provided"})

            # Initialize minioClient with an endpoint and keys.
            try:
                minioClient = Minio(SERVER_ENDPOINT,
                                access_key=auth.get("access_key"),
                                secret_key=auth.get("secret_key"),
                                secure=False)

                if request.form.get('data'):
                    data = json.loads(request.form.get('data'))
                    new_bucket_name = data.get('new_bucket_name')
                    minioClient.make_bucket(new_bucket_name)
                    return jsonify({"new_bucket_name":new_bucket_name})
                else:
                    return jsonify({"err":"Invalid request."})
            except ResponseError as err:
                return jsonify({"err":str(err)})
            except (InvalidAccessKeyId, AccessDenied, SignatureDoesNotMatch) as err:
                return jsonify({"err":"Invalid Authentication."})
            except BucketAlreadyOwnedByYou as err:
                return jsonify({"err":str(err)})
            except JSONDecodeError:
                return jsonify({"err":"Incorrect formatting of data field."})
            except (InvalidBucketError, TypeError) as err:
                return jsonify({"err":"Please enter a valid new_bucket_name."})






    #*************************************************************************************************************************************************************
    #Create an endpoint for metadata
    #*************************************************************************************************************************************************************






    @app.route('/minio_metadata', methods=['GET'])
    def minio_metadata():
        if request.method == 'GET':

            if minio_keys(request):
                auth = minio_keys(request)
                if "err" in auth:
                    return jsonify(auth)
            else:
                return jsonify({"err": "No authentication keys provided"})

            minioClient = Minio(SERVER_ENDPOINT,
                                    access_key=auth.get("access_key"),
                                    secret_key=auth.get("secret_key"),
                                    secure=False)

            config = json.loads(request.form.get('config'))
            deposit_id = config.get('deposit_id')
            bucket_name = config.get('bucket_name')

            try:
                obj = minioClient.get_object(bucket_name, deposit_id)
            except NoSuchKey as err:
                return jsonify({"err":"The requested deposit_id does not exist"})
            except (AccessDenied, InvalidAccessKeyId, SignatureDoesNotMatch):
                return jsonify({"err":"Invalid Authentication."})

            #check whether object exists in the bucket
            meta_obj = minioClient.fget_object(bucket_name,object_name=deposit_id,file_path=deposit_id)
            ret_object =   {"metadata": str(meta_obj.metadata), 
                            "deposit_id": str(meta_obj.object_name), 
                            "modified": str(meta_obj.last_modified),
                            "etag": str(meta_obj.etag), 
                            "size": str(meta_obj.size), 
                            "content_type": str(meta_obj.content_type)}
            return jsonify(ret_object)

    return app