#!/usr/bin/env bash
export OS_AUTH_URL=https://pegasus.sky.oslomet.no:5000
export OS_PROJECT_ID=33573bfebdd4444397efff218012ffff
export OS_PROJECT_NAME="ACIT4410_H25_jonon4120"
export OS_USER_DOMAIN_NAME="oslomet"
if [ -z "$OS_USER_DOMAIN_NAME" ]; then unset OS_USER_DOMAIN_NAME; fi
export OS_PROJECT_DOMAIN_ID="4ad72e8d0e39443bace1d059b8458827"
if [ -z "$OS_PROJECT_DOMAIN_ID" ]; then unset OS_PROJECT_DOMAIN_ID; fi
unset OS_TENANT_ID
unset OS_TENANT_NAME
export OS_USERNAME="jonon4120@oslomet.no"
echo "Please enter your OpenStack Password for project $OS_PROJECT_NAME as user $OS_USERNAME: "
read -sr OS_PASSWORD_INPUT
export OS_PASSWORD=$OS_PASSWORD_INPUT
export OS_REGION_NAME="Pilestredet"
if [ -z "$OS_REGION_NAME" ]; then unset OS_REGION_NAME; fi
export OS_INTERFACE=public
export OS_IDENTITY_API_VERSION=3
