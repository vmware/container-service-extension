// container-service-extension
// Copyright (c) 2017 VMware, Inc. All Rights Reserved.
// SPDX-License-Identifier: BSD-2-Clause

package govcd

import (
  "fmt"
  "encoding/xml"
  "io/ioutil"
  "net/http"
  "net/url"
  "crypto/tls"
  "strconv"
  "log"
)

type Credentials struct {
  user      string
  org       string
  password  string
}

type Client struct {
  HRef          url.URL
  VersionInfo   *VersionInfo
  Token         string
  Insecure      bool
  Http          *http.Client
}

type SupportedVersions struct {
  XMLName xml.Name `xml:"http://www.vmware.com/vcloud/versions SupportedVersions"`
  Versions  []VersionInfo `xml:"http://www.vmware.com/vcloud/versions VersionInfo"`
}

type VersionInfo struct {
  XMLName xml.Name `xml:"VersionInfo"`
  Deprecated bool `xml:"deprecated,attr"`
  Version string `xml:"Version"`
  LoginUrl string `xml:LoginUrl`
}

func Versions(client *Client) *SupportedVersions{
  sv := new(SupportedVersions)
  doRequest(client, "GET", "/api/versions", nil, sv)
  return sv
}

func SetHighestVersion(client *Client){
  v := Versions(client)
  h := 0.0
  var hv VersionInfo
  for _, value := range v.Versions {
    if ! value.Deprecated {
      f, _ := strconv.ParseFloat(value.Version, 64)
      if f > h{
        hv = value
        h = f
      }
    }
  }
  client.VersionInfo = &hv
}

func SetVersion(client *Client, version string){
  client.VersionInfo = new(VersionInfo)
  client.VersionInfo.Version = version
  client.VersionInfo.LoginUrl = fmt.Sprintf("%s%s", client.HRef.String(), "/api/sessions")
}

func setSessionEndpoints(){
  // for _, link := range s.Link {
  //   fmt.Println(link.Type, link.ID, link.Name)
  // }
}

func SetCredentials(client *Client, credentials Credentials) error {
  if client.VersionInfo == nil {
    SetHighestVersion(client)
  }
  u, _ := url.Parse(client.VersionInfo.LoginUrl)
  s := new(Session)
  resp, err := doRequest(client, "POST", u.Path, &credentials, s)
  if err != nil {
    return err
  }
  client.Token = resp.Header.Get("x-vcloud-authorization")
  log.Output(2, fmt.Sprintf("token=%s", client.Token))
  return nil
}

func RehydrateFromToken(client *Client, token string){
  
}

// TODO(parse error responses)
func doRequest(client *Client, method string, path string, credentials *Credentials, out interface{}) (*http.Response, error) {
  if client.Http == nil {
    tr := &http.Transport{
      TLSClientConfig: &tls.Config{InsecureSkipVerify : client.Insecure},
    }
    client.Http = &http.Client{Transport: tr}
  }
  hr := client.HRef
  hr.Path = path
  req, err := http.NewRequest(method, hr.String(), nil)
  if err != nil {
    return nil, err
  }
  if credentials != nil {
    req.SetBasicAuth(fmt.Sprintf("%s@%s", credentials.user, credentials.org), credentials.password)
  }
  if client.VersionInfo != nil {
    req.Header.Add("Accept", fmt.Sprintf("application/*+xml;version=%s", client.VersionInfo.Version))
  }
  resp, err := client.Http.Do(req)
  if err != nil {
    log.Output(2, fmt.Sprintf("%s, error=%s", hr.String(), err))
    return resp, err
  }
  defer resp.Body.Close()
  htmlData, err := ioutil.ReadAll(resp.Body)
  if err != nil {
    str := fmt.Sprintf("%s, error=%s", hr.String(), err)
    log.Output(2, str)
    return resp, err
  }
  log.Output(2, fmt.Sprintf("%s, rc=%d", hr.String(), resp.StatusCode))
  xml.Unmarshal(htmlData, &out)
  return resp, nil
}

func GetResource(client *Client){

}
