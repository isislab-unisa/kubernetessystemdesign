# Internet-facing application deployment

Design and deploy an application with its internal Service and expose it externally using the Kubernetes Gateway API with path-based routing rules.

This category includes the following learning objectives:
- Understanding of Pods.
- Understanding of Deployments.
- Understanding of ClusterIP Services.
- Understanding of the Gateway API and how a Gateway sits in front of Services.

## Setup

The Gateway API requires two things to work:
- The Custom Resource Definitions (CRDs) that define the resource types.
- A Gateway controller that watches those resources and programs the actual data plane.

The tasks in this category use [NGINX Gateway Fabric](https://docs.nginx.com/nginx-gateway-fabric) as the Gateway controller.

### Install the Gateway API CRDs

The Gateway API is not bundled with Kubernetes by default, but we can reference the [documentation](https://gateway-api.sigs.k8s.io/guides/getting-started/#installing-a-gateway-controller) for installation instructions.

Install the standard Gateway API CRDs:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml
```

Verify that the Gateway API CRDs were created:

```bash
kubectl get crds | grep gateway.networking.k8s.io
```

The output should include the following core Gateway API resource types:

```bash
gatewayclasses.gateway.networking.k8s.io    2026-03-05T10:00:00Z
gateways.gateway.networking.k8s.io          2026-03-05T10:00:00Z
httproutes.gateway.networking.k8s.io        2026-03-05T10:00:00Z
```

### Install NGINX Gateway Fabric

Install the NGINX Gateway Fabric CRDs:

```bash
kubectl apply -f https://raw.githubusercontent.com/nginx/nginx-gateway-fabric/v1.6.2/deploy/crds.yaml
```

Verify that the NGINX Gateway Fabric CRDs were created:

```bash
kubectl get crds | grep gateway.nginx.org
```

The output should include the following NGINX Gateway Fabric resource types:

```bash
nginxgateways.gateway.nginx.org          2026-03-05T10:00:00Z
nginxproxies.gateway.nginx.org           2026-03-05T10:00:00Z
observabilitypolicies.gateway.nginx.org  2026-03-05T10:00:00Z
```

Deploy NGINX Gateway Fabric:

```bash
kubectl apply -f https://raw.githubusercontent.com/nginx/nginx-gateway-fabric/v1.6.2/deploy/default/deploy.yaml
```

Wait for the controller to be ready:

```bash
kubectl wait --timeout=5m -n nginx-gateway \
    deployment/nginx-gateway \
    --for=condition=Available
```

The controller's name may change in future releases, so if the above command fails, run the following to find the correct name:

```bash
kubectl get deployment -n nginx-gateway
```

Verify that the `nginx` GatewayClass is available:

```bash
kubectl get gatewayclass
```

The output should show the `nginx` GatewayClass in `Accepted` state:

```bash
NAME    CONTROLLER                                      ACCEPTED   AGE
nginx   gateway.nginx.org/nginx-gateway-controller      True       1m
```

## Task 1: Design and deploy a public-facing application with path-based routing

Your team needs to expose two internal services to external users through a single entry point. The application consists of a main dashboard and an admin panel, each running as an independent Deployment. A Gateway sits in front of both Services and routes incoming traffic to the correct backend based on the request path: `/dashboard` for the main dashboard and `/admin` for the admin panel.

Each service must be reachable only within the cluster through a ClusterIP Service. The Gateway is the only component that accepts external traffic.

### Architectural design

The task requires two independent applications reachable from outside the cluster through a single entry point, with path-based routing to direct traffic to the correct backend. Each application must remain internal (ClusterIP only), and only the Gateway accepts external traffic. These constraints drive four design decisions:

1. Each application runs as its own Deployment with one replica. Keeping the dashboard and the admin panel in separate Deployments means they can be scaled, updated, and rolled back independently. Each Deployment creates a ReplicaSet that manages a single Pod.

2. Each Deployment is connected with a ClusterIP Service (`dashboard-svc` and `admin-svc`) to provide a stable cluster-internal DNS name and load-balance traffic to the Pods. They accept requests on port `80` and forward them to the container port `8080`. Because ClusterIP has no external port, neither service is reachable from outside the cluster on its own.

3. A Gateway resource (`app-gateway`) is the single externally accessible component. It listens for HTTP traffic on port `80` and is backed by the `nginx` gateway. In bare-metal environments the controller exposes a NodePort Service, giving external clients a reachable port on the node IP.

4. An HTTPRoute resource (`app-routes`) binds to the Gateway and defines the path-based routing rules. Requests to `/dashboard` are forwarded to `dashboard-svc`, and requests to `/admin` are forwarded to `admin-svc`. A URL rewrite filter strips the path prefix before the request reaches the backend, so each application receives traffic at `/` regardless of the original path.

![Architecture diagram](images/internet-facing-application-deployment.png)

The diagram shows the resulting architecture: external clients send HTTP requests to the Gateway, which is the only component with an externally accessible port. The HTTPRoute inspects the request path and forwards traffic to the correct ClusterIP Service, which in turn reaches the Pod managed by the corresponding Deployment. The two application Services have no external route, so they are unreachable from outside the cluster without the Gateway.

### Implementation

#### Deploy the applications

We start by creating the two Deployments. The `MESSAGE` environment variable sets a custom message in each [hello-kubernetes](https://hub.docker.com/r/paulbouwer/hello-kubernetes) instance, making it easy to distinguish which service is responding.

```bash
kubectl create deployment dashboard \
    --image=paulbouwer/hello-kubernetes:1.10 \
    --port=8080
kubectl set env deployment/dashboard MESSAGE="Main Dashboard"
```

```bash
kubectl create deployment admin \
    --image=paulbouwer/hello-kubernetes:1.10 \
    --port=8080
kubectl set env deployment/admin MESSAGE="Admin Panel"
```

Next, we expose each Deployment as a ClusterIP Service:

```bash
kubectl expose deployment dashboard \
    --name=dashboard-svc \
    --type=ClusterIP \
    --port=80 \
    --target-port=8080
```

```bash
kubectl expose deployment admin \
    --name=admin-svc \
    --type=ClusterIP \
    --port=80 \
    --target-port=8080
```

#### Create the gateway

We create a Gateway resource that listens for HTTP traffic on port `80`. The `gatewayClassName: nginx` field references the GatewayClass provided by the installed Gateway controller:

```bash
cat <<EOF > gateway.yaml
```

With the following content:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: app-gateway
spec:
  gatewayClassName: nginx
  listeners:
    - name: http
      protocol: HTTP
      port: 80
EOF
```

To verify the file was created correctly, run:

```bash
cat gateway.yaml
```

Apply the Gateway manifest:

```bash
kubectl apply -f gateway.yaml
```

#### Create the HTTP routes

We create an HTTPRoute resource that defines the path-based routing rules and binds them to the Gateway:

```bash
cat <<EOF > httproute.yaml
```

With the following content:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-routes
spec:
  parentRefs:
    - name: app-gateway
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /dashboard
      filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /
      backendRefs:
        - name: dashboard-svc
          port: 80
    - matches:
        - path:
            type: PathPrefix
            value: /admin
      filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /
      backendRefs:
        - name: admin-svc
          port: 80
EOF
```

A few things to note in this manifest:

- **Parent reference**: `parentRefs` binds this HTTPRoute to the `app-gateway` Gateway, so the controller knows which Gateway should serve these routing rules.
- **Path-based routing**: Each rule matches a path prefix and forwards traffic to the corresponding backend Service.
- **URL rewrite filter**: The `URLRewrite` filter with `ReplacePrefixMatch: /` strips the path prefix before forwarding the request to the backend, so the application receives requests at `/` regardless of the original path. For example, a request to `/dashboard/home` is forwarded to the backend as `/home`, and a request to `/dashboard` is forwarded as `/`.

To verify the file was created correctly, run:

```bash
cat httproute.yaml
```

Apply the HTTPRoute manifest:

```bash
kubectl apply -f httproute.yaml
```

#### Verify resource creation

To verify that the Pods are running, execute:

```bash
kubectl get pods -l app=dashboard
kubectl get pods -l app=admin
```

The output for each should look similar to this:

```bash
NAME                         READY   STATUS    RESTARTS   AGE
dashboard-6bfbf8b67c-jv8tv   1/1     Running   0          1m
```

To verify that the Services are configured correctly, run:

```bash
kubectl get svc dashboard-svc admin-svc
```

The output should look similar to this:

```bash
NAME            TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
dashboard-svc   ClusterIP   10.96.45.12    <none>        80/TCP    1m
admin-svc       ClusterIP   10.96.78.34    <none>        80/TCP    1m
```

To verify that the Gateway is programmed, run:

```bash
kubectl get gateway app-gateway
```

The output should look similar to this:

```bash
NAME          CLASS   ADDRESS   PROGRAMMED   AGE
app-gateway   nginx             True         1m
```

**Note**: In bare-metal environments there is no cloud load balancer to assign an external IP, so the `ADDRESS` field will be empty. Traffic is still reachable through the node IP and the NodePort assigned to the Gateway Service.

To verify that the HTTPRoute is bound to the Gateway and accepted, run:

```bash
kubectl get httproute app-routes
```

The output should look similar to this:

```bash
NAME         HOSTNAMES   AGE
app-routes               1m
```

#### Test path-based routing

Store the node IP and the NodePort assigned to the Gateway Service in variables for convenience:

```bash
NODE_IP=$(kubectl get nodes \
    -o jsonpath='{.items[0].status.addresses[0].address}')
echo $NODE_IP
```

```bash
NODE_PORT=$(kubectl get svc -n nginx-gateway \
    -o jsonpath='{.items[0].spec.ports[0].nodePort}')
echo $NODE_PORT
```

Send a request to the `/dashboard` path:

```bash
curl -s http://$NODE_IP:$NODE_PORT/dashboard | grep -A2 'message'
```

The output should show the `Main Dashboard` message:

```html
<div id="message">
  Main Dashboard
</div>
```

Send a request to the `/admin` path:

```bash
curl -s http://$NODE_IP:$NODE_PORT/admin | grep -A2 'message'
```

The output should show the `Admin Panel` message:

```html
<div id="message">
  Admin Panel
</div>
```

This confirms that the Gateway is correctly routing requests to the appropriate backend Service based on the request path.

#### Verify that Services alone are not enough

ClusterIP Services are reachable within the cluster network, but they have no externally accessible port. To confirm this, compare the two Services against the Gateway Service:

```bash
kubectl get svc dashboard-svc admin-svc
```

```bash
kubectl get svc -n nginx-gateway
```

The output for the application Services will show `ClusterIP` type with no external IP and no NodePort:

```bash
NAME            TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
dashboard-svc   ClusterIP   10.96.45.12    <none>        80/TCP    5m
admin-svc       ClusterIP   10.96.78.34    <none>        80/TCP    5m
```

The Gateway Service, by contrast, exposes a NodePort that external clients can reach:

```bash
NAME            TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
nginx-gateway   NodePort   10.96.11.22    <none>        80:31234/TCP   5m
```

A client outside the cluster has no route to a ClusterIP address, so the application Services are unreachable from the outside regardless of whether they are running. The Gateway is the only component with an externally accessible port, and it acts as the single controlled entry point that forwards traffic to the correct internal Service based on the request path.

#### Configure Killercoda port forwarding to access the application from the browser

If you are running this scenario in Killercoda, you can test the application from the terminal using `curl` as shown above, but you can also access it directly from the browser using Killercoda's traffic forwarding feature.

Run the following command to forward the Gateway Service port to port `8080` on the node:

```bash
kubectl port-forward -n nginx-gateway svc/nginx-gateway 8080:80 --address 0.0.0.0
```

While the command is running, open the Killercoda traffic forwarding panel:
1. Click the **Traffic / Ports** tab at the top of the Killercoda interface.
2. Enter `8080` in the port field and click **Access**.

A new browser tab will open pointing to the Killercoda-provided URL for port `8080`. Append the path to the URL in the browser address bar to reach each service:
- `<killercoda-url>/dashboard` — should display the `Main Dashboard` page.
- `<killercoda-url>/admin` — should display the `Admin Panel` page.

To stop the port forwarding, press `Ctrl+C` in the terminal.
