import ssl
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from lxml import etree

SOAP_URL = "https://eservices.eopyy.gov.gr/hospitalisationWSS_UGn_EU-hospitalisationWSS_UGn_EU-context-root/MainWSClassPort"
USERNAME = "wsepirus2026"
PASSWORD = "Wsepirus@@2026"

class EOPYY_TLS12_Adapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers(
            "ECDHE-RSA-AES256-GCM-SHA384:"
            "ECDHE-RSA-AES128-GCM-SHA256:"
            "AES256-GCM-SHA384:"
            "AES128-GCM-SHA256"
        )
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)

def submit_hl7(hl7_message):
    try:
        hl7_message = hl7_message.replace("\r\n", "\r").replace("\n", "\r")
        hl7_cdata = etree.CDATA(hl7_message)

        envelope = etree.Element(
            "{http://schemas.xmlsoap.org/soap/envelope/}Envelope",
            nsmap={
                "soap-env": "http://schemas.xmlsoap.org/soap/envelope/",
                "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
                "ns0": "http://bean.intracom.com/"
            }
        )

        header = etree.SubElement(envelope, "{http://schemas.xmlsoap.org/soap/envelope/}Header")
        security = etree.SubElement(header, "{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Security")
        token = etree.SubElement(security, "{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}UsernameToken")

        user = etree.SubElement(token, "{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Username")
        user.text = USERNAME

        pwd = etree.SubElement(token, "{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Password")
        pwd.set("Type", "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText")
        pwd.text = PASSWORD

        body = etree.SubElement(envelope, "{http://schemas.xmlsoap.org/soap/envelope/}Body")
        method = etree.SubElement(body, "{http://bean.intracom.com/}saveAdmissionHl7")
        arg0 = etree.SubElement(method, "arg0")
        hl7_node = etree.SubElement(arg0, "hl7ADT")
        hl7_node.text = hl7_cdata

        xml_payload = etree.tostring(envelope, encoding="utf-8", xml_declaration=True)

        session = Session()
        session.mount("https://", EOPYY_TLS12_Adapter())

        response = session.post(
            SOAP_URL,
            data=xml_payload,
            headers={"Content-Type": "text/xml; charset=utf-8"},
            timeout=30
        )

        return response.text

    except Exception as e:
        return f"Submission error: {e}"
