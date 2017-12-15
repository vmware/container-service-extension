// container-service-extension
// Copyright (c) 2017 VMware, Inc. All Rights Reserved.
// SPDX-License-Identifier: BSD-2-Clause


package main

import (
	"errors"
	"flag"
	"os"
	"path"

	"github.com/golang/glog"
	"github.com/kubernetes-incubator/external-storage/lib/controller"

	"k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/wait"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"syscall"
)

const (
	provisionerName = "vmware.com/vcloud-director"
)

type vcdProvisioner struct {
	pvDir string
	identity string
}

func NewVCDProvisioner() controller.Provisioner {
	nodeName := os.Getenv("NODE_NAME")
	if nodeName == "" {
		glog.Fatal("env variable NODE_NAME must be set so that this provisioner can identify itself")
	}
	glog.Infof("Starting new provisioner, name=%s, on node: %s", provisionerName, nodeName)
	return &vcdProvisioner{
		pvDir:    "/tmp/vcd-provisioner",
		identity: nodeName,
	}
}

var _ controller.Provisioner = &vcdProvisioner{}

func (p *vcdProvisioner) Provision(options controller.VolumeOptions) (*v1.PersistentVolume, error) {

	glog.Infof("Starting new provisioner, name=%s, on node: %s", provisionerName, nodeName)

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
	ann, ok := volume.Annotations["vcdProvisionerIdentity"]
	if !ok {
		return errors.New("identity annotation not found on PV")
	}
	if ann != p.identity {
		return &controller.IgnoredError{Reason: "identity annotation on PV does not match ours"}
	}

	path := path.Join(p.pvDir, volume.Name)
	if err := os.RemoveAll(path); err != nil {
		return err
	}

	return nil
}

func main() {
	syscall.Umask(0)

	flag.Parse()
	flag.Set("logtostderr", "true")

	config, err := rest.InClusterConfig()
	if err != nil {
		glog.Fatalf("Failed to create config: %v", err)
	}
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		glog.Fatalf("Failed to create client: %v", err)
	}

	serverVersion, err := clientset.Discovery().ServerVersion()
	if err != nil {
		glog.Fatalf("Error getting server version: %v", err)
	}

	glog.Infof("Starting vcd-provisioner")

	vcdProvisioner := NewVCDProvisioner()

	pc := controller.NewProvisionController(clientset, provisionerName, vcdProvisioner, serverVersion.GitVersion)
	pc.Run(wait.NeverStop)
}
