// container-service-extension
// Copyright (c) 2017 VMware, Inc. All Rights Reserved.
// SPDX-License-Identifier: BSD-2-Clause

package govcd

import (
    "fmt"
    "testing"
    "net/url"
    "log"
    "os"
)

var client Client
var credentials Credentials

func init() {
  client = Client{
      HRef: url.URL{
          Scheme: "https",
          Host: os.Getenv("VCD_HOST"),
      },
      Insecure: true,
  }
  credentials = Credentials{
      user: os.Getenv("VCD_USER"),
      org: os.Getenv("VCD_ORG"),
      password: os.Getenv("VCD_PASSWORD"),
  }
}

func TestGetVersions(t *testing.T) {
  v := Versions(&client)
  for _, value := range v.Versions {
    if ! value.Deprecated {
      log.Output(2, fmt.Sprintf("v=%s, dep=%t, url=%s", value.Version, value.Deprecated, value.LoginUrl))
    }
  }
}

func TestGetHighestVersion(t *testing.T) {
  SetHighestVersion(&client)
  log.Output(2, fmt.Sprintf("highest version: v=%s, dep=%t, url=%s", client.VersionInfo.Version, client.VersionInfo.Deprecated, client.VersionInfo.LoginUrl))
}

func TestLoginDefault(t *testing.T) {
  err := SetCredentials(&client, credentials)
  if err != nil {
    t.Errorf("login failed")
  }
}

func TestLoginWithVersion(t *testing.T) {
  SetVersion(&client, "29.0")
  err := SetCredentials(&client, credentials)
  if err != nil {
    t.Errorf("login failed")
  }
}
