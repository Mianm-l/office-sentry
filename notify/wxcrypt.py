# notify/wxcrypt.py
import base64
import struct
import hashlib
import os
import xml.etree.ElementTree as ET
from Crypto.Cipher import AES
import logging

logger = logging.getLogger("OfficeSentry.WXCrypt")

class PKCS7Encoder:
    """提供基于 32 字节块大小的 PKCS7 算法的加解密"""
    block_size = 32

    @classmethod
    def encode(cls, text_bytes: bytes) -> bytes:
        amount_to_pad = cls.block_size - (len(text_bytes) % cls.block_size)
        if amount_to_pad == 0:
            amount_to_pad = cls.block_size
        pad_chr = bytes([amount_to_pad])
        return text_bytes + pad_chr * amount_to_pad

    @classmethod
    def decode(cls, decrypted_bytes: bytes) -> bytes:
        pad = decrypted_bytes[-1]
        if pad < 1 or pad > cls.block_size:
            pad = 0
        return decrypted_bytes[:-pad]

class WXBizMsgCrypt:
    """
    企业微信/微信公众平台消息加解密适配器 (支持微信插件直接对话)
    """
    def __init__(self, token: str, encoding_aes_key: str, corpid: str):
        self.token = token
        self.encoding_aes_key = encoding_aes_key
        self.corpid = corpid
        self.key = base64.b64decode(encoding_aes_key + "=")
        assert len(self.key) == 32, "EncodingAESKey 长度非法 (必须为43位字符串)"

    def _get_sha1(self, *args) -> str:
        """生成安全签名"""
        sort_list = sorted(list(args))
        sha = hashlib.sha1()
        sha.update("".join(sort_list).encode("utf-8"))
        return sha.hexdigest()

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        """
        验证企业微信配置回调 URL (GET 请求)
        验证成功返回解密后的明文 echostr，验证失败抛出异常
        """
        signature = self._get_sha1(self.token, timestamp, nonce, echostr)
        if signature != msg_signature:
            raise ValueError(f"签名校验失败 (计算: {signature}, 收到: {msg_signature})")

        cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        decrypted = cipher.decrypt(base64.b64decode(echostr))
        unpadded = PKCS7Encoder.decode(decrypted)

        # 格式: 16位随机字符串 + 4位正文长度 + 正文明文 + receiveid/corpid
        msg_len = struct.unpack(">I", unpadded[16:20])[0]
        msg = unpadded[20:20 + msg_len].decode("utf-8")
        from_corpid = unpadded[20 + msg_len:].decode("utf-8")

        if from_corpid != self.corpid:
            logger.warning(f"CorpID 不一致: 期望 {self.corpid}, 收到 {from_corpid}")
        return msg

    def decrypt_msg(self, post_xml: str, msg_signature: str, timestamp: str, nonce: str) -> str:
        """
        检验消息的真实性并解密收到的企业微信 XML (POST 请求)
        """
        root = ET.fromstring(post_xml)
        encrypt_node = root.find("Encrypt")
        if encrypt_node is None:
            raise ValueError("缺少 Encrypt 密文节点")
        encrypt_b64 = encrypt_node.text.strip()

        # 验证签名
        signature = self._get_sha1(self.token, timestamp, nonce, encrypt_b64)
        if signature != msg_signature:
            raise ValueError("签名校验失败")

        cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        decrypted = cipher.decrypt(base64.b64decode(encrypt_b64))
        unpadded = PKCS7Encoder.decode(decrypted)

        msg_len = struct.unpack(">I", unpadded[16:20])[0]
        xml_content = unpadded[20:20 + msg_len].decode("utf-8")
        return xml_content

    def encrypt_msg(self, reply_xml: str, nonce: str, timestamp: str) -> str:
        """
        将明文回复 XML 加密打包为企业微信需要的密文 XML
        """
        random_16 = os.urandom(16)
        xml_bytes = reply_xml.encode("utf-8")
        msg_len_bytes = struct.pack(">I", len(xml_bytes))
        corpid_bytes = self.corpid.encode("utf-8")

        raw_payload = random_16 + msg_len_bytes + xml_bytes + corpid_bytes
        padded_payload = PKCS7Encoder.encode(raw_payload)

        cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        encrypted_bytes = cipher.encrypt(padded_payload)
        encrypt_b64 = base64.b64encode(encrypted_bytes).decode("utf-8")

        signature = self._get_sha1(self.token, timestamp, nonce, encrypt_b64)

        return f"""<xml>
<Encrypt><![CDATA[{encrypt_b64}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
