// container-service-extension
// Copyright (c) 2017 VMware, Inc. All Rights Reserved.
// SPDX-License-Identifier: BSD-2-Clause

package main

import (
  "flag"
  "fmt"
  "os"
  "path/filepath"
  "time"
  "io/ioutil"

  "encoding/json"

  "github.com/golang/glog"
  "github.com/kubernetes-incubator/external-storage/lib/controller"
  "k8s.io/client-go/kubernetes"
  "k8s.io/client-go/tools/clientcmd"
  "k8s.io/apimachinery/pkg/util/wait"
  "k8s.io/client-go/pkg/api/v1"
  metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

const (
  resyncPeriod              = 15 * time.Second
  provisionerName           = "vmware.com/vcloud-director"
  exponentialBackOffOnError = false
  failedRetryThreshold      = 5
  leasePeriod               = controller.DefaultLeaseDuration
  retryPeriod               = controller.DefaultRetryPeriod
  renewDeadline             = controller.DefaultRenewDeadline
  termLimit                 = controller.DefaultTermLimit
)

type vcdProvisioner struct {
  msgDir string
  pvDir string
  identity string
}

type vcdProvisionerResponse struct {
  PVName string
  Node string
}

func NewVcdProvisioner() controller.Provisioner {
  nodeName := os.Getenv("HOST")
  if nodeName == "" {
    glog.Fatal("env variable HOST must be set so that this provisioner can identify itself")
  }
  msgDir := os.Getenv("CSE_MSG_DIR")
  if msgDir == "" {
    glog.Fatal("env variable CSE_MSG_DIR must be set")
  }
  return &vcdProvisioner{
    msgDir:   msgDir,
    pvDir:    "/tmp/vcd-provisioner",
    identity: nodeName,
  }
}

var _ controller.Provisioner = &vcdProvisioner{}
var clientset *kubernetes.Clientset

func check(e error) {
    if e != nil {
        panic(e)
    }
}

func (p *vcdProvisioner) Provision(options controller.VolumeOptions) (*v1.PersistentVolume, error) {
  var target_node string
  marshalled, _ := json.MarshalIndent(options, "", "    ")
  fmt.Printf("vcdProvisioner->Provision called with options:\n%s\n", marshalled)
  request_file_name := fmt.Sprintf("%s/req/%s.json", p.msgDir, options.PVName)
  response_file_name := fmt.Sprintf("%s/res/%s.json", p.msgDir, options.PVName)
  f, err := os.Create(request_file_name)
  check(err)
  defer f.Close()
  _, err = f.Write(marshalled)
  check(err)
  fmt.Printf("request sent: %s\n", request_file_name)

  for {
    time.Sleep(5 * time.Second)
    response, err := ioutil.ReadFile(response_file_name)
    if err != nil {
      fmt.Printf("respnse wait: %s\n", response_file_name)
    } else {
      fmt.Printf("respnse read: %s\n", response_file_name)
      var r vcdProvisionerResponse
      json.Unmarshal(response, &r)
      marshalled, _ = json.MarshalIndent(r, "", "    ")
      fmt.Printf("response got: %s\n%s\n", r.PVName, marshalled)
      target_node = r.Node
      // pvname = r.PVName
      os.Remove(response_file_name)
      break
    }
  }

  label := fmt.Sprintf("pvc.%s", options.PVC.ObjectMeta.Name)

  n := clientset.CoreV1().Nodes()
  nodes, err := n.List(metav1.ListOptions{})
  for i, node := range nodes.Items {
    if node.Name == target_node {
      fmt.Printf("assigned to node: %s\n", node.ObjectMeta.Name)
      // node.Labels["idisks"] = pvname
      node.Labels[label] = ""
      n.Update(&nodes.Items[i])
    }
  }

  host_path := "/tmp"

	pv := &v1.PersistentVolume{
		ObjectMeta: metav1.ObjectMeta{
			Name: options.PVName,
			Annotations: map[string]string{
				"vcdProvisionerIdentity": p.identity,
			},
      Labels: map[string]string{
        "Node": target_node,
			},
		},
		Spec: v1.PersistentVolumeSpec{
			PersistentVolumeReclaimPolicy: options.PersistentVolumeReclaimPolicy,
			AccessModes:                   options.PVC.Spec.AccessModes,
			Capacity: v1.ResourceList{
				v1.ResourceName(v1.ResourceStorage): options.PVC.Spec.Resources.Requests[v1.ResourceName(v1.ResourceStorage)],
			},
			PersistentVolumeSource: v1.PersistentVolumeSource{
				HostPath: &v1.HostPathVolumeSource{
					Path: host_path,
				},
			},
		},
  }
  return pv, nil
}

func (p *vcdProvisioner) Delete(volume *v1.PersistentVolume) error {
  target_node := volume.ObjectMeta.Labels["Node"]
  pvc_name := volume.Spec.ClaimRef.Name

  marshalled, _ := json.MarshalIndent(volume, "", "    ")
  fmt.Printf("vcdProvisioner->Delete called with volume:\n%s\n", marshalled)
  fmt.Printf("pv: %s\npvc: %s\nnode: %s\n",
             volume.ObjectMeta.Name,
             pvc_name,
             target_node)
  label := fmt.Sprintf("pvc.%s", pvc_name)
  n := clientset.CoreV1().Nodes()
  nodes, _ := n.List(metav1.ListOptions{})
  for _, node := range nodes.Items {
    if node.Name == target_node {
      fmt.Printf("assigned to node: %s\n", node.ObjectMeta.Name)
      new_labels := map[string]string{}
      for k, v := range node.Labels {
        if k != label {
          new_labels[k] = v
        }
      }
      node.Labels = new_labels
      marshalled, _ = json.MarshalIndent(new_labels, "", "    ")
      fmt.Printf("new labels:\n%s\n", marshalled)
      marshalled, _ = json.MarshalIndent(node, "", "    ")
      fmt.Printf("modified node:\n%s\n", marshalled)
      n.Update(&node)
    }
  }

  return nil
}

func main() {
  var kubeconfig *string
  if home := homeDir(); home != "" {
    kubeconfig = flag.String("kubeconfig", filepath.Join(home, ".kube", "config"), "(optional) absolute path to the kubeconfig file")
  } else {
    kubeconfig = flag.String("kubeconfig", "", "absolute path to the kubeconfig file")
  }
  flag.Parse()

  config, err := clientcmd.BuildConfigFromFlags("", *kubeconfig)
  if err != nil {
    panic(err.Error())
  }

  clientset, err = kubernetes.NewForConfig(config)
  if err != nil {
    panic(err.Error())
  }

  serverVersion, err := clientset.Discovery().ServerVersion()
  if err != nil {
    glog.Fatalf("Error getting server version: %v", err)
  }
  fmt.Printf("Cluster version: %s\n", serverVersion)

  nodes, err := clientset.CoreV1().Nodes().List(metav1.ListOptions{})
  fmt.Printf("nodes: (%d)\n", len(nodes.Items))
  for _, node := range nodes.Items {
    fmt.Printf(" node: %s\n", node.ObjectMeta.Name)
  }

  vcdProvisioner := NewVcdProvisioner()

  pc := controller.NewProvisionController(clientset, resyncPeriod, provisionerName,
    vcdProvisioner, serverVersion.GitVersion, exponentialBackOffOnError,
    failedRetryThreshold, leasePeriod, renewDeadline, retryPeriod, termLimit)
  pc.Run(wait.NeverStop)

}

func homeDir() string {
  if h := os.Getenv("HOME"); h != "" {
    return h
  }
  return os.Getenv("USERPROFILE") // windows
}
