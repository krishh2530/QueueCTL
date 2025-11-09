from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_mysqldb import MySQL
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.automap import automap_base
from sqlalchemy import text, update, or_, exc
import datetime
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, wait,FIRST_COMPLETED
import subprocess
import queue

#initialise the Flask application and add database URI to the config
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://<username>:<password>@localhost/QueueCTL' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#initialise the database instance
db = SQLAlchemy(app)
Base = automap_base()
#CORS policy allows requests from any IP address
cors = CORS(app, origins='*')

#prepare the automap base
with app.app_context():
   Base.prepare(db.engine, reflect=True)

#initialise table classes
Jobs = Base.classes.jobs
Dlq = Base.classes.dlq

#create global threadpool instance, will be used to manage worker threads throughout the application
global executor
executor = ThreadPoolExecutor()
#function to gracefully shutdown and reset the threadpool
def executor_reset():
    global executor
    executor.shutdown(wait=True)
    executor = ThreadPoolExecutor()

#global configuration parameters
global max_retries, base_time
max_retries = 3
base_time = 2

#main function to be executed by worker threads
#Handles retry mechanism with exponential backoff, logs status updates to the database
def worker_function(job,db):
    with app.app_context():
        while job['attempts']<max_retries:
            job['attempts']+=1
            result = subprocess.run(job['command'],shell=True,capture_output=True,text=True)
            db.session.query(Jobs).filter(Jobs.id == job['id']).update({"attempts":job["attempts"]})
            if result.returncode==0:   #check for successful execution
                db.session.commit()
                return True
            else:
                print("ENTERING RETRY, Job id: ",job['id']," Attempt: ",job['attempts'])
                # db.session.query(Jobs).filter(Jobs.id == job['id']).update({"state":"processing","attempts":job['attempts']})
                delay = base_time ** job['attempts']
                time.sleep(delay)
                continue
        db.session.commit()
        return False

#thread-safe job queue instantiation
job_queue = queue.Queue()

#on server startup, restore pending jobs from the database based on status (processing and pending)
with app.app_context():
    existing_jobs = db.session.query(Jobs).filter(or_(Jobs.state == 'pending',Jobs.state=='processing')).all()
    existing_jobs = [{'id':job.id,'command':job.command,'max_retries':job.max_retries,'attempts':job.attempts} for job in existing_jobs]
    for i in existing_jobs:
        job_queue.put(i)
    print("Restored jobs to queue: ",list(job_queue.queue))

#route to queue a new job, adds the job to queue and logs it min database
@app.route('/enqueue',methods=['POST'])
def enqueue_job():
    try:
        data = request.get_json()
        data_for_worker = {"id":data["id"],"command":data["command"],'max_retries':max_retries,"attempts":0}
        job_queue.put(data_for_worker)
        print("Current queue: ",list(job_queue.queue))
        new_job = Jobs(
            id = data['id'],
            command = data['command'],
            max_retries = max_retries
        )
        db.session.add(new_job)
        db.session.commit()
        return jsonify({"message":"Job enqueued succesfully"}),200
    except exc.IntegrityError as e:
        return jsonify({"message":"ID already exists","error":str(e)}),500

#route to start worker threads, managaes job assignment, spawns as many workers as specified by user
@app.route('/worker/start',methods=['POST'])
def start_workers():
    data = request.get_json()
    num_workers = data['num_workers'] or 3
    executor._max_workers = num_workers
    future_to_job = {}
    for _ in range(min(num_workers, job_queue.qsize())):  #initial assignment of jobs based on number of jobs and available workers
        job = job_queue.get()
        future = executor.submit(worker_function,job,db)
        future_to_job[future] = job
        db.session.query(Jobs).filter(Jobs.id == job['id']).update({"state":"processing"})
        db.session.commit()

    while future_to_job:
        done, _ = wait(future_to_job.keys(), return_when=FIRST_COMPLETED)   #waits for at least one future(job) to complete before entering the loop
        # futures1, futures2, futures3 = futures
        for future in done:
            job = future_to_job.pop(future)
            # print(future.result())
            success = future.result()
            if success:
                print("SUCCESS, job id: ",job['id'])
                db.session.query(Jobs).filter(Jobs.id == job['id']).update({"state":"completed"})
                db.session.commit()
            else:
                print("Job with job id ",job['id']," failed")
                db.session.query(Jobs).filter(Jobs.id == job['id']).update({"state":"failed"})
                new_dlq_entry = Dlq(
                        id = job['id'],
                        command = job['command'],
                        created_at = db.session.get(Jobs,job['id']).created_at
                    )
                db.session.add(new_dlq_entry)
                db.session.commit()
            
            if not job_queue.empty():   #continue the loop if new jobs have been added to the queue
                next_job = job_queue.get()
                next_future = executor.submit(worker_function, next_job)
                future_to_job[next_future] = next_job
            else :
                break
                
                    
    return jsonify({"message":"Workers started"}),200

#gracefully shutdown all worker threads
@app.route('/worker/stop',methods= ['POST'])
def stop_workers():
    executor_reset()                #function defined above
    return jsonify({"message":"Workers stopped"}),200

#route to update the configuration parameters for retry mechanism
@app.route('/config',methods=['POST'])
def update_config():
    data = request.get_json()
    global max_retries, base_time
    if 'max_retries' in list(data.keys()):
        max_retries = data['max_retries'] or max_retries
    elif 'base_time' in list(data.keys()):
        base_time = data['base_time'] or base_time
    print(max_retries,' ',base_time)
    return jsonify({"message":"configuration updated"}),200

#route to fetch and display all the DLQ entries
@app.route('/dlq/list',methods=['GET'])
def get_dlq():
    dlq_entries = db.session.query(Dlq).all()
    dlq_list = [{'id':entry.id,'command':entry.command,'created_at':entry.created_at} for entry in dlq_entries]
    return jsonify(dlq_list),200

#route to retry jobs in the DLQ by adding them back to the job queue
@app.route('/dlq/retry',methods=['POST'])
def dlq_retry():
    data = request.get_json()
    dlq_entry = db.session.query(Dlq).filter(Dlq.id == data['id']).first()
    if dlq_entry:
        job_data = {'id':dlq_entry.id,'command':dlq_entry.command,'attempts':0,'max_retries':max_retries}
        db.session.query(Jobs).filter(Jobs.id == job_data['id']).update({'state':"pending",'attempts':0})
        db.session.delete(dlq_entry)
        job_queue.put(job_data)
        db.session.commit()
        return jsonify({"message":"Job moved from DLQ back to queue"}),200
    else:
        return jsonify({"message":"DLQ entry not found"}),404

#route to fetch and show all the jobs along with their status and so on
@app.route('/status',methods=['GET'])
def get_status():
    jobs = db.session.query(Jobs).all()
    jobs_list = [{'id':job.id,'command':job.command,'state':job.state,'attempts':job.attempts,'created_at':job.created_at,'updated_at':job.updated_at} for job in jobs]
    return jsonify(jobs_list),200

#route to list the jobs filtered by their status
@app.route('/list',methods=['GET'])
def get_jobs():
    data = request.get_json()
    query = data['status']
    job_list = db.session.query(Jobs).filter(Jobs.state == query).all()
    jobs = [{'id':job.id,'command':job.command,'state':job.state,'attempts':job.attempts,'created_at':job.created_at,'updated_at':job.updated_at} for job in job_list]
    return jsonify(jobs),200

if __name__ == "__main__":
    app.run(debug = True)  #start the application