
.PHONY: image

IMAGE?=vcd-provisioner
USERNAME?=pacogomez

image: vcd-provisioner
	docker build -t $(IMAGE) -f Dockerfile .
	docker tag $(IMAGE) docker.io/$(USERNAME)/$(IMAGE)

push: image
	docker push $(USERNAME)/$(IMAGE)

vcd-provisioner: $(shell find . -name "*.go")
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -a -ldflags '-extldflags "-static"' -o $(IMAGE) .

.PHONY: clean
clean:
	rm -rf vendor
	rm vcd-provisioner
	rm vcd-provisioner.docker
