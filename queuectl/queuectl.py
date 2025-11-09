import click
import requests
import subprocess
import sys
import json

SERVER = "http://localhost:5000"


#sets the base command for the tool
@click.group()
def queuectl():
    '''Command line tool for Job Queue Management'''
    pass

#create a command group
@queuectl.group()
def dlq():
    '''Commands to manage the Deal Letter Queue (DLQ)'''
    click.echo("use arguments list/retry to view or manage the DLQ")

@dlq.command()
def list():
    '''list all entries int he DLQ'''
    response = requests.get(f"{SERVER}/dlq/list")
    if response.status_code == 200:
        dlq_entries = response.json()
        for entry in dlq_entries:
            click.echo("ID: {id}, Command: {command}, Created At: {created_at}".format(**entry))
        
    else: 
        click.echo("Failed to fetch from DLQ")

@dlq.command()
@click.argument("job_id")
def retry(job_id):
    '''Rertry a job from the DLQ'''
    click.echo(f"Retrying job with ID: {job_id} from DLQ")
    response = requests.post(f"{SERVER}/dlq/retry", json={"id": int(job_id)})
    if response.status_code == 200:
        click.echo("Job moved successfully into queue")
    else:
        click.echo("Failed")

@queuectl.group()
def config():
    '''Command to set the configuration parameters'''
    click.echo("Use the set command to update configs - max_retries or base_time")

@config.command()
@click.argument("key")
@click.argument("value")
def set(key,value):
    '''Set configuration parameters'''
    data = {key:int(value)}
    response = requests.post(f"{SERVER}/config",json=data)
    if response.status_code == 200:
        click.echo("Parameters updated")
    else:
        click.echo("Failed to update")
    
@queuectl.command()
def status():
    '''Gets status of all the jobs and workers'''
    response = requests.get(f"{SERVER}/status")
    if response.status_code == 200:
        data = response.json()
        for i in data:
            click.echo("ID: {id}, Command: {command}, State: {state}, Attempts: {attempts}, Created At: {created_at}, Last Updated: {updated_at}".format(**i))

    else:
        click.echo("Failed to fetch jobs")

@queuectl.command()
@click.option("--state",default=None,help="filter jobs by state")
def list(state):
    data = {"status":state}
    response = requests.get(f"{SERVER}/list",json=data)
    if response.status_code == 200:
        resp = response.json()
        for i in resp:
            click.echo("ID: {id}, Command: {command}, State: {state}, Attempts: {attempts}, Created At: {created_at}, Last Updated: {updated_at}".format(**i))
    else:
        click.echo("Failed to fetch")

@queuectl.command()
def enqueue():
    '''This argument is used to enqueue jobs'''
    click.echo("Enqueue jobs by giving it in this format: {'id':XX, 'command':'XXXX'}")

@queuectl.command()
@click.option("--id", required=True, type=int)
@click.option("--command", required=True)
def enqueue(id,command):
    data = {"id": id, "command": command}
    click.echo(data)
    response = requests.post(f"{SERVER}/enqueue",json=data)
    if response.status_code == 200:
        click.echo("Jop enqueued successfully")
    else:
        r = response.json()
        resp = r['message']
        click.echo("Faild to enqueue job: {resp}".format(resp=resp))
    

@queuectl.group()
def worker():
    '''command to start or stop workers'''
    click.echo("Use start or stop commands for workers")

@worker.command("start")
@click.option("--count",default=2,help="Number of workers to spawn",type=int)
def start(count):
    data = {"num_workers":count}
    r = requests.post(f"{SERVER}/worker/start",json=data)
    if r.status_code == 200:
        click.echo("Workers have started")
    else:
        click.echo("Failed to start workers")

@worker.command()
def stop():
    r = requests.post(f"{SERVER}/worker/stop")
    if r.status_code == 200:
        click.echo("Workers stopped successfully")
    else:
        click.echo("Failed to stop workers")

if __name__ == "__main__":
    queuectl()