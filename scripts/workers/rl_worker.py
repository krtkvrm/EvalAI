# import kubernetes
import logging
import os
import time
import signal
# import uuid
from .worker_util import (
    EvalAI_Interface
)

import random
import string

from kubernetes import client, config


def randomString(stringLength=10):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True


logger = logging.getLogger(__name__)

AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "04ba82647ca42da7e24247001ed83d6a5e9002a3")
ENVIRONMENT_IMAGE = os.environ.get("AUTH_TOKEN", "04ba82647ca42da7e24247001ed83d6a5e9002a3")
DJANGO_SERVER = os.environ.get("DJANGO_SERVER", "https://hard-treefrog-35.localtunnel.me")
DJANGO_SERVER_PORT = os.environ.get("DJANGO_SERVER_PORT", "443")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "random-number-generator-challenge-220302f3-e640-45b8-855d-ac73d5f6ba14")

DEPLOYED_SUBMISSIONS = set()

DEPLOYMENT_NAME = randomString(6)


def create_deployment_object(image, submission, message):
    # Configure Pod template container
    e = client.V1EnvVar(
        name="PYTHONUNBUFFERED",
        value="1",
    )
    e_env = client.V1EnvVar(
        name="AUTH_TOKEN",
        value=AUTH_TOKEN
    )
    e_env_url = client.V1EnvVar(
        name="DJANGO_SERVER",
        value=DJANGO_SERVER
    )
    e_env_ids = client.V1EnvVar(
        name="BODY",
        value=str(message)
    )
    agent_container = client.V1Container(
        name="agent",
        image=image,
        env=[e]
    )
    environment_container = client.V1Container(
        name="environment",
        image="vkartik97/env:latest",
        env=[e, e_env, e_env_url, e_env_ids]
    )
    # Create and configurate a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "evaluation"}),
        spec=client.V1PodSpec(containers=[environment_container, agent_container]))
    # Create the specification of deployment
    spec = client.ExtensionsV1beta1DeploymentSpec(
        replicas=1,
        template=template)
    # Instantiate the deployment object
    deployment = client.ExtensionsV1beta1Deployment(
        api_version="extensions/v1beta1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name="submission-{0}".format(submission)),
        spec=spec)

    return deployment


def create_deployment(api_instance, deployment):
    # Create deployement
    api_response = api_instance.create_namespaced_deployment(
        body=deployment,
        namespace="default")
    print("Deployment created. status='%s'" % str(api_response.status))


def process_submission_callback(message, api):
    config.load_kube_config()
    extensions_v1beta1 = client.ExtensionsV1beta1Api()
    print(message)
    submission_data = {
        "submission_status": "running",
        "submission": message["submission_pk"],
    }
    print(submission_data)
    api.update_submission_status(submission_data, message["challenge_pk"])
    dep = create_deployment_object(
        message["submitted_image_uri"],
        message["submission_pk"],
        message
    )
    create_deployment(extensions_v1beta1, dep)
    # print(create_deployment_object())


def main():
    # print(create_deployment_object())
    api = EvalAI_Interface(
        AUTH_TOKEN=AUTH_TOKEN,
        DJANGO_SERVER=DJANGO_SERVER,
        DJANGO_SERVER_PORT=DJANGO_SERVER_PORT,
        QUEUE_NAME=QUEUE_NAME,
    )
    # print(api.get_challenge_by_queue_name())
    print("String RL Worker for {}".format(api.get_challenge_by_queue_name()["title"]))
    killer = GracefulKiller()
    logger.info(
        "RL Submission Worker Started"
    )
    while True:
        print("YES")
        logger.info(
            "Fetching new messages from the queue {}".format(QUEUE_NAME)
        )
        
        message = api.get_message_from_sqs_queue()
        print(message)
        message_body = message.get("body")
        if message_body:
            submission_pk = message_body.get("submission_pk")
            submission = api.get_submission_by_pk(submission_pk)
            if submission:
                if submission.get("status") == "finished":
                    message_receipt_handle = message.get("receipt_handle")
                    api.delete_message_from_sqs_queue(message_receipt_handle)
                elif submission.get("status") == "running":
                    continue
                else:
                    message_receipt_handle = message.get("receipt_handle")
                    logger.info(
                        "Processing message body: {}".format(message_body)
                    )

                    print(message_body)
                    process_submission_callback(message_body, api)
                    # Let the queue know that the message is processed
                    api.delete_message_from_sqs_queue(message.get("receipt_handle"))
        time.sleep(5)
        if killer.kill_now:
            break


if __name__ == "__main__":
    main()
    logger.info("Quitting Submission Worker.")
