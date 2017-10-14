// container-service-extension
// Copyright (c) 2017 VMware, Inc. All Rights Reserved.
// SPDX-License-Identifier: BSD-2-Clause

package govcd

type Link struct {
  HREF string `xml:"href,attr"`
  ID   string `xml:"id,attr,omitempty"`
  Type string `xml:"type,attr,omitempty"`
  Name string `xml:"name,attr,omitempty"`
  Rel  string `xml:"rel,attr"`
}

type Session struct {
  Link []*Link `xml:"Link"`
}
