

PhotonOS 2.0
```shell
tdnf install -y build-essential python3-setuptools python3-tools python3-pip gcc glibc-devel glibc-lang binutils python3-devel linux-api-headers gawk
tdnf install -y git go-1.9.1-1.ph2
 mkdir -p go/src/github.com/vmware/container-service-extension/pv
 cp /usr/lib/python3.6/site-packages/cse/* ~go/src/github.com/vmware/container-service-extension/
```

Ubuntu 16.04
```shell
/usr/bin/growpart /dev/sda 1
/sbin/resize2fs /dev/sda1
apt-get install -y golang-go
mkdir -p /root/go/bin
mkdir -p /root/go/src/github.com/vmware/container-service-extension/pv
export GOPATH=/root/go
export PATH=$GOPATH/bin:$PATH
curl https://glide.sh/get | sh
cp {glide.yaml, glide.lock, vcd-provider.go} /root/go/src/github.com/vmware/container-service-extension/pv
```


```shell
$ export GOPATH=/root/go
$ glide install --strip-vendor
$ go build
$ ./pv
```
