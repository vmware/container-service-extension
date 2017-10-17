// container-service-extension
// Copyright (c) 2017 VMware, Inc. All Rights Reserved.
// SPDX-License-Identifier: BSD-2-Clause

package main

import (
  "flag"
  "fmt"
  "os"
  "path"
  "path/filepath"
  "time"

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
  pvDir string
  identity string
}

func NewVcdProvisioner() controller.Provisioner {
  nodeName := os.Getenv("HOST")
  if nodeName == "" {
    glog.Fatal("env variable HOST must be set so that this provisioner can identify itself")
  }
  return &vcdProvisioner{
    pvDir:    "/tmp/vcd-provisioner",
    identity: nodeName,
  }
}

var _ controller.Provisioner = &vcdProvisioner{}

func (p *vcdProvisioner) Provision(options controller.VolumeOptions) (*v1.PersistentVolume, error) {
  fmt.Printf("provision called with options:\n%+v\n", options)

  path := path.Join(p.pvDir, options.PVName)

	if err := os.MkdirAll(path, 0777); err != nil {
		return nil, err
	}

	pv := &v1.PersistentVolume{
		ObjectMeta: metav1.ObjectMeta{
			Name: options.PVName,
			Annotations: map[string]string{
				"vcdProvisionerIdentity": p.identity,
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
					Path: path,
				},
			},
		},
  }
  return pv, nil
}

func (p *vcdProvisioner) Delete(volume *v1.PersistentVolume) error {
  fmt.Printf("delete called\n")
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

  clientset, err := kubernetes.NewForConfig(config)
  if err != nil {
    panic(err.Error())
  }

  serverVersion, err := clientset.Discovery().ServerVersion()
  if err != nil {
    glog.Fatalf("Error getting server version: %v", err)
  }
  fmt.Printf("Cluster version: %s\n", serverVersion)

  nodes, err := clientset.CoreV1().Nodes().List(metav1.ListOptions{})
  for _, node := range nodes {
    fmt.Printf("%+v\n", node)
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
