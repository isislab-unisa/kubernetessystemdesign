# Single-container deployment

Design and deploy a simple single-container application with a service for internal access.

This category includes the following learning objectives:
- Understanding of Pods.
- Understanding of Deployments.
- Understanding of ClusterIP services.

## Task 1: Design and deploy an internal dashboard

Your team needs an internal monitoring dashboard that runs inside the cluster and shows, at any time, the node and namespace they are working in.

The dashboard must be packaged as a single container image ([paulbouwer/hello-kubernetes dashboard](https://hub.docker.com/r/paulbouwer/hello-kubernetes)). It does not need to be highly resilient, since brief periods of unavailability are acceptable.

However, other services inside the cluster need a stable address to reach it, so Pod IPs alone are not enough. Make sure the dashboard is strictly for internal use and not accessible from outside the cluster.

### Architectural design

### Implementation

We start by creating a Deployment with a single replica (the default). The task allows short periods of unavailability, so one instance is enough. We use the `paulbouwer/hello-kubernetes:1.10` image and declare that the container listens on port `8080`. The `kubectl create deployment` command automatically adds the label `app=hello-dashboard` to the Pods, which will be useful later when we create the Service.

```bash
kubectl create deployment hello-dashboard \
    --image=paulbouwer/hello-kubernetes:1.10 \
    --port=8080
```

Next, we expose the Deployment as a ClusterIP Service. ClusterIP is the right choice here because it gives other services inside the cluster a stable address for reaching the dashboard while keeping it inaccessible from outside.

We use `kubectl expose` instead of creating the Service manually with `kubectl create service clusterip` because it automatically sets the selector to match the Deployment Pods, which is exactly the wiring we need. The Service listens on port `80` and forwards traffic to the container port `8080`.

```bash
kubectl expose deployment hello-dashboard \
    --name=hello-dashboard-svc \
    --type=ClusterIP \
    --port=80 \
    --target-port=8080
```

#### Verify resource creation

To verify that the Pod is running, execute the following command, which filters Pods by the `app=hello-dashboard` label automatically set by `kubectl create deployment`:

```bash
kubectl get pods -l app=hello-dashboard
```

The output should look similar to this:

```bash
NAME                               READY   STATUS    RESTARTS   AGE
hello-dashboard-6bfbf8b67c-jv8tv   1/1     Running   0          16m
```

To verify that the Service is configured correctly, run:

```bash
kubectl get svc hello-dashboard-svc
```

The output should look similar to this:

```bash
NAME                  TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
hello-dashboard-svc   ClusterIP   10.111.28.77   <none>        80/TCP    15
```

From this output, we can confirm that internal access to the dashboard is available at [http://hello-dashboard-svc:80](http://hello-dashboard-svc:80) and that external access is not possible, since no external IP is assigned.

#### Test the dashboard

To test the dashboard, create a temporary Pod using [busybox](https://hub.docker.com/_/busybox):

```bash
kubectl run -it --rm --restart=Never busybox --image=busybox sh
```

Inside the busybox Pod, use `wget` to access the dashboard through the Service ClusterIP. The dashboard should respond with an HTML page containing cluster information.

```bash
wget -qO- http://hello-dashboard-svc
```

The dashboard HTML should look similar to the example below:

```html
<!DOCTYPE html>
<html>
    <head>
        <title>Hello Kubernetes!</title>
        <!-- CSS styles omitted for brevity -->
    </head>
    <body>
        <div class="main">
            <!-- Content omitted for brevity -->
            <div class="content">
                <div id="message">Hello world!</div>
                <div id="info">
                <table>
                    <tr><th>namespace:</th><td>-</td></tr>
                    <tr><th>pod:</th><td>hello-dashboard-6bfbf8b67c-jv8tv</td></tr>
                    <tr><th>node:</th><td>- (Linux 6.8.0-94-generic)</td></tr>
                </table>
                </div>
            </div>
        </div>
    </body>
</html>
```
