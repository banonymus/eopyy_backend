def submit_discarge_hl7(hl7_message):
    try:
        import ssl, re
        from requests import Session
        from requests.adapters import HTTPAdapter
        from urllib3.util.ssl_ import create_urllib3_context
        from lxml import etree

        SOAP_URL = "https://eservices.eopyy.gov.gr/hospitalisationWSS_UGn_EU-hospitalisationWSS_UGn_EU-context-root/MainWSClassPort"
        USERNAME = "wsepirus2026"
        PASSWORD = "Wsepirus@@2026"

        class _TLS12Adapter(HTTPAdapter):
            def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
                ctx = create_urllib3_context()
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                ctx.maximum_version = ssl.TLSVersion.TLSv1_2
                try:
                    ctx.set_ciphers(
                        "ECDHE-RSA-AES256-GCM-SHA384:"
                        "ECDHE-RSA-AES128-GCM-SHA256:"
                        "AES256-GCM-SHA384:"
                        "AES128-GCM-SHA256"
                    )
                except Exception:
                    pass
                pool_kwargs["ssl_context"] = ctx
                return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

            def proxy_manager_for(self, *args, **kwargs):
                kwargs.setdefault("ssl_context", create_urllib3_context())
                return super().proxy_manager_for(*args, **kwargs)

        # Normalize HL7 terminators to CR-only and remove BOM
        hl7_message = hl7_message.replace("\r\n", "\r").replace("\n", "\r")
        hl7_message = hl7_message.replace("\ufeff", "")

        # Build SOAP envelope with correct namespaces and UsernameToken
        NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
        NS_WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
        NS_BEAN = "http://bean.intracom.com/"

        envelope = etree.Element("{%s}Envelope" % NS_SOAP,
                                 nsmap={
                                     "soapenv": NS_SOAP,
                                     "wsse": NS_WSSE,
                                     "bean": NS_BEAN
                                 })
        header = etree.SubElement(envelope, "{%s}Header" % NS_SOAP)
        security = etree.SubElement(header, "{%s}Security" % NS_WSSE)
        token = etree.SubElement(security, "{%s}UsernameToken" % NS_WSSE)

        user = etree.SubElement(token, "{%s}Username" % NS_WSSE)
        user.text = USERNAME

        pwd = etree.SubElement(token, "{%s}Password" % NS_WSSE)
        pwd.set("Type", "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText")
        pwd.text = PASSWORD

        body = etree.SubElement(envelope, "{%s}Body" % NS_SOAP)
        # operation for discharge; change element name if you need another operation
        method = etree.SubElement(body, "{%s}saveDischargeHl7" % NS_BEAN)
        arg0 = etree.SubElement(method, "arg0")
        hl7_node = etree.SubElement(arg0, "hl7ADT")
        hl7_node.text = etree.CDATA(hl7_message)

        xml_payload = etree.tostring(envelope, encoding="utf-8", xml_declaration=True)

        session = Session()
        session.mount("https://", _TLS12Adapter())

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "Content-Length": str(len(xml_payload)),
            "SOAPAction": ""
        }

        resp = session.post(SOAP_URL, data=xml_payload, headers=headers, timeout=30, verify=True)
        return resp.text

    except Exception as e:
        return f"Submission error: {e}"
