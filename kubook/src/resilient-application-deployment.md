# Resilient application deployment

Design and deploy an application and configure it to run with multiple replicas across the cluster.

This category includes the following learning objectives:
- Understanding of Pods.
- Understanding of Deployments.
- Understanding of ReplicaSets.

## Task 1: Design and deploy a resilient web server with multiple replicas

Your team needs an internal web server that must remain available even when individual Pod instances fail or are rescheduled. The service must continue serving requests without manual intervention.

The web server must run as an [nginx](https://hub.docker.com/_/nginx) container with three replicas to ensure availability across failures. Other services inside the cluster need a stable address to reach it, but it must not be accessible from outside the cluster.

### Architectural design

The task requires an internal web server that stays available across Pod failures without manual intervention, and must be reachable only from inside the cluster. These constraints drive three design decisions:

1. A Deployment with three replicas ensures the web server remains available even when individual Pods fail or are rescheduled. The Deployment creates a ReplicaSet that continuously reconciles the actual number of running Pods with the desired count. If a Pod crashes or is evicted, the ReplicaSet controller detects the mismatch and immediately schedules a replacement, restoring full capacity without manual intervention.

2. Other services need a stable address to reach the web server. Pod IPs change every time a Pod is recreated, and with three replicas there are three different IPs at any given moment. A ClusterIP Service (`nginx-resilient-svc`) solves both problems: it provides a fixed cluster-internal DNS name and load-balances traffic across all healthy replicas, so callers are unaffected by individual Pod restarts or rescheduling.

3. The web server must not be accessible from outside the cluster. A ClusterIP Service has no external port and no route from outside the cluster network, so it satisfies this requirement by design. No Gateway, Ingress, or NodePort is needed.

![Architecture diagram](images/resilient-application-deployment.png)

The diagram shows the resulting architecture: external clients have no path into the application, while internal services reach the web server through the ClusterIP Service, which load-balances traffic across the three Pod replicas managed by the Deployment's ReplicaSet.

### Implementation

We start by creating a Deployment with three replicas. The `--replicas=3` flag tells the Deployment controller to keep three Pod instances running at all times. If a Pod crashes or is deleted, the controller will automatically create a replacement to restore the desired count.

```bash
kubectl create deployment nginx-resilient \
    --image=nginx:1.27 \
    --port=80 \
    --replicas=3
```

To inspect the YAML that would be applied without actually creating the resource, use the `--dry-run=client -o yaml` flags:

```bash
kubectl create deployment nginx-resilient \
    --image=nginx:1.27 \
    --port=80 \
    --replicas=3 \
    --dry-run=client -o yaml
```

The output should look similar to this:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  creationTimestamp: null
  labels:
    app: nginx-resilient
  name: nginx-resilient
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx-resilient
  strategy: {}
  template:
    metadata:
      creationTimestamp: null
      labels:
        app: nginx-resilient
    spec:
      containers:
      - image: nginx:1.27
        name: nginx
        ports:
        - containerPort: 80
        resources: {}
status: {}
```

Next, we expose the Deployment as a ClusterIP Service. The Service gives other cluster workloads a single stable address that load-balances across all three Pod replicas, so callers are unaffected by individual Pod restarts or rescheduling.

```bash
kubectl expose deployment nginx-resilient \
    --name=nginx-resilient-svc \
    --type=ClusterIP \
    --port=80 \
    --target-port=80
```

#### Verify resource creation

To verify that all three Pods are running, execute:

```bash
kubectl get pods -l app=nginx-resilient
```

The output should show three Pods in the `Running` state:

```bash
NAME                                READY   STATUS    RESTARTS   AGE
nginx-resilient-7d6b8f9c4d-4k2pq    1/1     Running   0          1m
nginx-resilient-7d6b8f9c4d-r9fxz    1/1     Running   0          1m
nginx-resilient-7d6b8f9c4d-tn8wl    1/1     Running   0          1m
```

To verify that the Service is configured correctly, run:

```bash
kubectl get svc nginx-resilient-svc
```

The output should look similar to this:

```bash
NAME                  TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
nginx-resilient-svc   ClusterIP   10.96.204.17   <none>        80/TCP    1m
```

#### Understand the Deployment, ReplicaSet, and Pod relationship

When a Deployment is created, Kubernetes automatically creates a ReplicaSet to manage the Pod instances. The Deployment owns the ReplicaSet, and the ReplicaSet owns the Pods. This three-level hierarchy is what makes self-healing possible: the ReplicaSet controller continuously reconciles the actual number of running Pods with the desired replica count specified in the Deployment.

To inspect the ReplicaSet that the Deployment created, run:

```bash
kubectl get replicasets -l app=nginx-resilient
```

The output should look similar to this:

```bash
NAME                          DESIRED   CURRENT   READY   AGE
nginx-resilient-7d6b8f9c4d    3         3         3       2m
```

The `DESIRED`, `CURRENT`, and `READY` columns all showing `3` confirms that the ReplicaSet has successfully started three Pod instances and all three are ready to serve traffic.

To inspect the full ownership chain from the Deployment down to a single Pod, run:

```bash
kubectl describe pod \
    $(kubectl get pods -l app=nginx-resilient \
        -o jsonpath='{.items[0].metadata.name}') \
    | grep 'Controlled By'
```

The output shows that the Pod is controlled by the ReplicaSet:

```bash
Controlled By:  ReplicaSet/nginx-resilient-7d6b8f9c4d
```

#### Verify self-healing behavior

To verify that the Deployment automatically replaces failed Pods, delete one of the running Pods:

```bash
POD_NAME=$(kubectl get pods \
    -l app=nginx-resilient \
    -o jsonpath='{.items[0].metadata.name}') \
&& echo $POD_NAME
```

```bash
kubectl delete pod $POD_NAME
```

To observe the replacement in real time, open a second terminal and watch the Pods:

```bash
kubectl get pods -l app=nginx-resilient --watch
```

Then delete the Pod in the first terminal. The watch output will show the deleted Pod terminating while a new one is already being created to replace it:

```bash
NAME                                READY   STATUS              RESTARTS   AGE
nginx-resilient-7d6b8f9c4d-4k2pq    0/1     Terminating         0          5m
nginx-resilient-7d6b8f9c4d-r9fxz    1/1     Running             0          5m
nginx-resilient-7d6b8f9c4d-tn8wl    1/1     Running             0          5m
nginx-resilient-7d6b8f9c4d-x7bmc    0/1     ContainerCreating   0          2s
```

Within a few seconds, all three Pods will be running again:

```bash
NAME                                READY   STATUS    RESTARTS   AGE
nginx-resilient-7d6b8f9c4d-r9fxz    1/1     Running   0          6m
nginx-resilient-7d6b8f9c4d-tn8wl    1/1     Running   0          6m
nginx-resilient-7d6b8f9c4d-x7bmc    1/1     Running   0          30s
```

This behavior is driven by the ReplicaSet controller detecting that the actual Pod count (two) is less than the desired count (three) and immediately scheduling a replacement.

#### Test the web server

To test that the Service correctly load-balances across the replicas, create a temporary Pod and send a request through the Service:

```bash
kubectl run -it --rm --restart=Never busybox --image=busybox sh
```

Inside the busybox Pod, use `wget` to send several requests through the Service:

```bash
for i in $(seq 1 9); do
    wget -qO- http://nginx-resilient-svc > /dev/null \
        && echo "request $i done"
done
```

Exit the busybox Pod, then check the access logs of each nginx replica:

```bash
for pod in $(kubectl get pods -l app=nginx-resilient -o name); do
    echo "=== $pod ==="
    kubectl logs $pod | grep "GET /"
done
```

The output shows each Pod's access log with only the requests it handled, confirming that the Service distributed traffic across all three replicas:

```bash
=== pod/nginx-resilient-7d6b8f9c4d-r9fxz ===
10.244.0.12 - - [05/Mar/2026:10:30:00 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
10.244.0.12 - - [05/Mar/2026:10:30:01 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
10.244.0.12 - - [05/Mar/2026:10:30:02 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
=== pod/nginx-resilient-7d6b8f9c4d-tn8wl ===
10.244.0.12 - - [05/Mar/2026:10:30:01 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
10.244.0.12 - - [05/Mar/2026:10:30:03 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
10.244.0.12 - - [05/Mar/2026:10:30:04 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
=== pod/nginx-resilient-7d6b8f9c4d-x7bmc ===
10.244.0.12 - - [05/Mar/2026:10:30:02 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
10.244.0.12 - - [05/Mar/2026:10:30:03 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
10.244.0.12 - - [05/Mar/2026:10:30:05 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
```

The Service acts as a stable endpoint regardless of how many Pods are running at any given moment, which means callers never need to track individual Pod IPs.
