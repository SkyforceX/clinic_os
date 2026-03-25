# crm/apps/api_his/serializers.py
from rest_framework import serializers

class AppointmentBriefSerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()
    ma_bn = serializers.CharField()
    ho_ten = serializers.CharField()
    ngay_sinh = serializers.DateField(allow_null=True)
    ten_cong_ty = serializers.CharField(allow_blank=True)
    ngay_hen_kham = serializers.DateField(allow_null=True)
