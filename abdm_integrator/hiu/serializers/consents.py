from rest_framework import serializers

from abdm_integrator.const import ConsentPurpose, HealthInformationType
from abdm_integrator.hiu.models import ConsentRequest
from abdm_integrator.serializers import (
    GatewayCallbackResponseBaseSerializer,
    GatewayCareContextSerializer,
    GatewayIdSerializer,
    GatewayPermissionSerializer,
    GatewayRequesterSerializer,
)
from abdm_integrator.utils import future_date_validator, past_date_validator


class GenerateConsentSerializer(serializers.Serializer):

    class PurposeSerializer(serializers.Serializer):
        code = serializers.ChoiceField(choices=ConsentPurpose.CHOICES)
        refUri = serializers.CharField(default=ConsentPurpose.REFERENCE_URI)
        text = serializers.SerializerMethodField(method_name='get_purpose_text')

        def get_purpose_text(self, obj):
            return next(x[1] for x in ConsentPurpose.CHOICES if x[0] == obj['code'])

    class PermissionSerializer(GatewayPermissionSerializer):
        class DateRangeSerializer(serializers.Serializer):
            vars()['from'] = serializers.DateTimeField(validators=[past_date_validator])
            to = serializers.DateTimeField(validators=[past_date_validator])

        dateRange = DateRangeSerializer()
        dataEraseAt = serializers.DateTimeField(validators=[future_date_validator])

    purpose = PurposeSerializer()
    patient = GatewayIdSerializer()
    hip = GatewayIdSerializer(required=False)
    hiu = GatewayIdSerializer()
    careContexts = serializers.ListField(required=False, child=GatewayCareContextSerializer(), min_length=1)
    requester = GatewayRequesterSerializer()
    hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HealthInformationType.CHOICES),
                                    min_length=1)
    permission = PermissionSerializer()


class ConsentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRequest
        exclude = ('gateway_request_id', )


class GatewayConsentRequestOnInitSerializer(GatewayCallbackResponseBaseSerializer):
    consentRequest = GatewayIdSerializer(required=False)
