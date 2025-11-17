from automation.data.termos_validacao_melhorados import validar_documento_melhorado

texto = """
CITY POLICE OFFICER
GUJRANWALA PAKISTAN
POLICE CHARACTER CERTIFICATE
No. GWJ-817018
Dated 19-08-2019
This is to certify that Mr ATIF JAVED
S/O JAVED
CNIC No. 34101-0291436-1
Passport No. DT8674362
Date Of Birth: 23-01-1992
Place & Period of stay as follows:
PLACE & PERIOD OF STAY
Stay Period
Address
Police Station
From
To
Permanent: SIALKOT ROAD, HOUSE NO.FC-228, STREET NO.2 MOHALLAH ISLAM COLONY, GUJRANWALA.
Civil Line Gujranwala
Since Birth
To Date
As per available record of Police Station(s), the applicant has:
· NO Criminal Record Found till date
Note:
· This Certificate may be used for the purpose of:
· Proceeding to Brazil
· This Certificate is valid for 180 days from the date of issuance.
· This is system generated document and does not require stamp & manual signature.
· The authenticity of this document can be verified through QR code or at https://pkm.punjab.gov.pk/verify
· This verification is based on the information provided by the applicant
CITY POLICE OFFICER
GUJRANWALA
· Permanent/Temporary Residence address to be based on Computerized National Identity Card (CNIC)
· For Feedback: PH No. 055-3821306
· Email: pkm.gujranwala@punjabpolice.gov.pk
"""

res = validar_documento_melhorado('Antecedentes_Origem', texto, minimo_confianca=70)
print('valido=', res['valido'])
print('confianca=', res['confianca'])
print('tem_negacao=', res.get('tem_negacao'))
print('motivo=', res.get('motivo'))
