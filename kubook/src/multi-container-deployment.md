# Multi-container deployment

Design and deploy a Pod with sidecar containers and a service for internal access.

This category includes the following learning objectives:
- Understanding of Pods.
- Understanding of Deployments.
- Knowledge of multi-container pod patterns and container lifecycle.
- Understanding of shared volumes between containers.

## Task 1: Design and deploy a web server with a logging sidecar

Your team needs an internal web server that serves a static page inside the cluster. The operations team also requires real-time visibility into the access logs of the web server without having to exec into the running container.

The web server must run as an [nginx](https://hub.docker.com/_/nginx) container. A second container running [busybox](https://hub.docker.com/_/busybox) must act as a logging sidecar that continuously reads the nginx access log and prints it to its own standard output.

The web server must be reachable from other services inside the cluster through a stable address, but it must not be accessible from outside the cluster.

### Architectural design

### Implementation

Unlike single-container Pods, multi-container Pods cannot be created with `kubectl create deployment` alone. We need a YAML manifest to define both containers and the shared volume within the same Pod.

We start by creating a file called `nginx-with-sidecar.yaml`:

```bash
cat <<EOF > nginx-with-sidecar.yaml
```

With the following content:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-with-sidecar
  labels:
    app: nginx-with-sidecar
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx-with-sidecar
  template:
    metadata:
      labels:
        app: nginx-with-sidecar
    spec:
      containers:
        - name: nginx
          image: nginx:1.27
          ports:
            - containerPort: 80
          volumeMounts:
            - name: logs
              mountPath: /var/log/nginx
        - name: log-sidecar
          image: busybox:1.37
          command:
            - sh
            - -c
            - tail -f /var/log/nginx/access.log
          volumeMounts:
            - name: logs
              mountPath: /var/log/nginx
      volumes:
        - name: logs
          emptyDir: {}
EOF
```

There are a few things to note in this manifest:

- **Shared volume**: An `emptyDir` volume called `logs` is mounted at `/var/log/nginx` in both containers. This is how the sidecar reads the log files written by nginx. An `emptyDir` volume is created when the Pod is assigned to a node and exists as long as the Pod is running on that node, making it ideal for sharing temporary data between containers in the same Pod.
- **Sidecar container**: The `log-sidecar` container runs `tail -f` on the nginx access log. This means it will continuously stream new log entries to its standard output, where they can be read with `kubectl logs`.
- **Single replica**: One replica is enough since brief unavailability is acceptable.

To verify the file was created correctly, run:

```bash
cat nginx-with-sidecar.yaml
```

Apply the manifest to create the Deployment:

```bash
kubectl apply -f nginx-with-sidecar.yaml
```

Next, we expose the Deployment as a ClusterIP Service. The Service listens on port `80` and forwards traffic to the nginx container port `80`.

```bash
kubectl expose deployment nginx-with-sidecar \
    --name=nginx-sidecar-svc \
    --type=ClusterIP \
    --port=80 \
    --target-port=80
```

#### Verify resource creation

To verify that the Pod is running and that both containers are ready, execute the following command:

```bash
kubectl get pods -l app=nginx-with-sidecar
```

The output should look similar to this. Notice that the `READY` column shows `2/2`, confirming that both the nginx container and the log-sidecar container are running:

```bash
NAME                                  READY   STATUS    RESTARTS   AGE
nginx-with-sidecar-5d4f7b8c9a-k2m8n   2/2     Running   0          2m
```

To verify that the Service is configured correctly, run:

```bash
kubectl get svc nginx-sidecar-svc
```

The output should look similar to this:

```bash
NAME                TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
nginx-sidecar-svc   ClusterIP   10.96.145.203   <none>        80/TCP    1m
```

#### Test the web server

To test the web server, create a temporary Pod and send a request through the Service:

```bash
kubectl run -it --rm --restart=Never busybox --image=busybox sh
```

Inside the busybox Pod, use `wget` to access the web server through the Service ClusterIP:

```bash
wget -qO- http://nginx-sidecar-svc
```

The response should be the default nginx welcome page:

```html
<!DOCTYPE html>
<html>
    <head>
        <title>Welcome to nginx!</title>
        <!-- CSS styles omitted for brevity -->
    </head>
    <body>
        <h1>Welcome to nginx!</h1>
        <p>If you see this page, the nginx web server is successfully installed and
        working. Further configuration is required.</p>
        <!-- Content omitted for brevity -->
    </body>
</html>
```

#### Verify the sidecar logs

After sending the request above, exit the busybox Pod and verify that the sidecar captured the access log entry. First, get the Pod name:

```bash
POD_NAME=$(kubectl get pods \
    -l app=nginx-with-sidecar \
    -o jsonpath='{.items[0].metadata.name}') \
&& echo $POD_NAME
```

Then, read the logs from the `log-sidecar` container using the `-c` flag to specify which container to read from:

```bash
kubectl logs $POD_NAME -c log-sidecar
```

The output should show the access log entry from the request we made through the busybox Pod:

```bash
10.244.0.12 - - [05/Mar/2026:10:30:00 +0000] "GET / HTTP/1.1" 200 615 "-" "Wget"
```

This confirms that the sidecar pattern is working correctly: nginx writes logs to the shared volume, and the sidecar reads and exposes them through its standard output.
