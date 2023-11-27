import requests
from django.db import transaction
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.status import HTTP_201_CREATED, HTTP_202_ACCEPTED

from abdm_integrator.const import ArtefactFetchStatus, ConsentStatus
from abdm_integrator.exceptions import (
    ERROR_CODE_REQUIRED,
    ERROR_CODE_REQUIRED_MESSAGE,
    ABDMGatewayError,
    ABDMServiceUnavailable,
    CustomError,
)
from abdm_integrator.hiu.const import ABHA_EXISTS_BY_HEALTH_ID_PATH, HIUGatewayAPIPath
from abdm_integrator.hiu.exceptions import HIUError
from abdm_integrator.hiu.models import ConsentArtefact, ConsentRequest
from abdm_integrator.hiu.serializers.consents import (
    ConsentArtefactSerializer,
    ConsentRequestSerializer,
    GatewayConsentRequestNotifySerializer,
    GatewayConsentRequestOnFetchSerializer,
    GatewayConsentRequestOnInitSerializer,
    GenerateConsentSerializer,
)
from abdm_integrator.hiu.tasks import process_hiu_consent_notification_request
from abdm_integrator.hiu.views.base import HIUBaseView, HIUGatewayBaseView
from abdm_integrator.utils import ABDMRequestHelper, APIResultsSetPagination


class GenerateConsent(HIUBaseView):
    def post(self, request, format=None):
        serializer = GenerateConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent_data = serializer.data
        self.check_if_health_id_exists(consent_data['patient']['id'])
        gateway_request_id = self.gateway_consent_request_init(consent_data)
        consent_request = self.save_consent_request(gateway_request_id, consent_data, request.user)
        return Response(status=HTTP_201_CREATED,
                        data=ConsentRequestSerializer(consent_request).data)

    def check_if_health_id_exists(self, health_id):
        try:
            payload = {'healthId': health_id}
            response = ABDMRequestHelper().abha_post(ABHA_EXISTS_BY_HEALTH_ID_PATH, payload)
            if not response.get('status'):
                raise CustomError(
                    error_code=HIUError.CODE_PATIENT_NOT_FOUND,
                    error_message=HIUError.CUSTOM_ERRORS[HIUError.CODE_PATIENT_NOT_FOUND],
                    detail_attr='patient.id'
                )
        # TODO Remove below exception handling once addressed on abha side
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            error = ABDMRequestHelper.gateway_json_from_response(err.response)
            raise ABDMGatewayError(error.get('code'), error.get('message'))

    def gateway_consent_request_init(self, consent_data):
        payload = ABDMRequestHelper.common_request_data()
        payload['consent'] = consent_data
        ABDMRequestHelper().gateway_post(HIUGatewayAPIPath.CONSENT_REQUEST_INIT, payload)
        return payload['requestId']

    def save_consent_request(self, gateway_request_id, consent_data, user):
        consent_request = ConsentRequest(user=user, gateway_request_id=gateway_request_id, details=consent_data)
        consent_request.update_user_amendable_details(consent_data['permission'], consent_data['hiTypes'])
        return consent_request


class GatewayConsentRequestOnInit(HIUGatewayBaseView):
    def post(self, request, format=None):
        GatewayConsentRequestOnInitSerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        consent_request = ConsentRequest.objects.get(
            gateway_request_id=request_data['resp']['requestId']
        )
        if request_data.get('consentRequest'):
            consent_request.consent_request_id = request_data['consentRequest']['id']
            consent_request.status = ConsentStatus.REQUESTED
        elif request_data.get('error'):
            consent_request.status = ConsentStatus.ERROR
            consent_request.error = request_data['error']
        consent_request.save()


class GatewayConsentRequestNotify(HIUGatewayBaseView):

    def post(self, request, format=None):
        GatewayConsentRequestNotifySerializer(data=request.data).is_valid(raise_exception=True)
        process_hiu_consent_notification_request.delay(request.data)
        return Response(status=HTTP_202_ACCEPTED)


class GatewayConsentRequestNotifyProcessor:

    def __init__(self, request_data):
        self.request_data = request_data

    def process_request(self):
        consent_status = self.request_data['notification']['status']
        if consent_status == ConsentStatus.REVOKED:
            return self.handle_revoked()
        consent_request = ConsentRequest.objects.get(
            consent_request_id=self.request_data['notification']['consentRequestId']
        )
        if consent_status == ConsentStatus.GRANTED:
            self.handle_granted(consent_request)
        elif consent_status == ConsentStatus.EXPIRED:
            self.handle_expired(consent_request)

    def handle_granted(self, consent_request):
        consent_artefacts = []
        with transaction.atomic():
            consent_request.update_status(ConsentStatus.GRANTED)
            for artefact in self.request_data['notification']['consentArtefacts']:
                consent_artefact, _ = ConsentArtefact.objects.get_or_create(artefact_id=artefact['id'],
                                                                            consent_request=consent_request)
                consent_artefacts.append(consent_artefact)

        for consent_artefact in consent_artefacts:
            if consent_artefact.fetch_status == ArtefactFetchStatus.PENDING:
                self.fetch_artefact_and_update_status(consent_artefact)

    @transaction.atomic
    def handle_expired(self, consent_request):
        artefact_ids = list(consent_request.artefacts.values_list('artefact_id', flat=True))
        consent_request.artefacts.all().delete()
        consent_request.update_status(ConsentStatus.EXPIRED)
        self.gateway_consents_on_notify(artefact_ids)

    @transaction.atomic
    def handle_revoked(self):
        artefact_ids = [artefact['id'] for artefact in self.request_data['notification']['consentArtefacts']]
        consent_request = ConsentRequest.objects.get(artefacts__artefact_id=artefact_ids[0])
        ConsentArtefact.objects.filter(artefact_id__in=artefact_ids).delete()
        if consent_request.artefacts.all().count() == 0:
            consent_request.update_status(ConsentStatus.REVOKED)
        self.gateway_consents_on_notify(artefact_ids)

    def fetch_artefact_and_update_status(self, consent_artefact):
        payload = ABDMRequestHelper.common_request_data()
        consent_artefact.gateway_request_id = payload['requestId']
        try:
            self.gateway_fetch_artefact_details(consent_artefact.artefact_id, payload)
            consent_artefact.fetch_status = ArtefactFetchStatus.REQUESTED
        except ABDMGatewayError as err:
            consent_artefact.error = err.error
            consent_artefact.fetch_status = ArtefactFetchStatus.ERROR
        consent_artefact.save()

    def gateway_fetch_artefact_details(self, artefact_id, payload):
        payload['consentId'] = artefact_id
        ABDMRequestHelper().gateway_post(HIUGatewayAPIPath.CONSENTS_FETCH, payload)
        return payload['requestId']

    def gateway_consents_on_notify(self, artefact_ids):
        payload = ABDMRequestHelper.common_request_data()
        payload['acknowledgement'] = [{'status': 'OK', 'consentId': artefact_id}
                                      for artefact_id in artefact_ids]
        payload['resp'] = {'requestId': self.request_data['requestId']}
        ABDMRequestHelper().gateway_post(HIUGatewayAPIPath.CONSENT_REQUEST_ON_NOTIFY, payload)
        return payload['requestId']


class GatewayConsentRequestOnFetch(HIUGatewayBaseView):

    def post(self, request, format=None):
        GatewayConsentRequestOnFetchSerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    @transaction.atomic
    def process_request(self, request_data):
        consent_artefact = ConsentArtefact.objects.get(gateway_request_id=request_data['resp']['requestId'])
        if request_data.get('consent'):
            consent_artefact.details = request_data['consent']['consentDetail']
            consent_artefact.fetch_status = ArtefactFetchStatus.RECEIVED
            if consent_artefact.consent_request.artefacts.filter(details__isnull=False).count() == 0:
                self.update_consent_request_from_artefact(consent_artefact)
        elif request_data.get('error'):
            consent_artefact.fetch_status = ArtefactFetchStatus.ERROR
            consent_artefact.error = request_data['error']
        consent_artefact.save()

    def update_consent_request_from_artefact(self, consent_artefact):
        consent_request = consent_artefact.consent_request
        consent_request.update_user_amendable_details(consent_artefact.details['permission'],
                                                      consent_artefact.details['hiTypes'])


class ConsentFetch(HIUBaseView, viewsets.ReadOnlyModelViewSet):
    serializer_class = ConsentRequestSerializer
    pagination_class = APIResultsSetPagination

    def get_queryset(self):
        queryset = ConsentRequest.objects.filter(user=self.request.user).order_by('-date_created')
        request_params = self.request.query_params
        if request_params.get('abha_id'):
            queryset = queryset.filter(details__patient__id=request_params['abha_id'])
        if request_params.get('status'):
            queryset = queryset.filter(status=request_params['status'])
        if request_params.get('from_date'):
            queryset = queryset.filter(health_info_to_date__date__gte=request_params['from_date'])
        if request_params.get('to_date'):
            queryset = queryset.filter(health_info_from_date__date__lte=request_params['to_date'])
        if request_params.get('search'):
            queryset = queryset.filter(Q(status__icontains=request_params['search']) |
                                       Q(health_info_types__icontains=request_params['search']))
        return queryset


class ConsentArtefactFetch(HIUBaseView, viewsets.ReadOnlyModelViewSet):
    serializer_class = ConsentArtefactSerializer
    pagination_class = APIResultsSetPagination

    def get_queryset(self):
        queryset = ConsentArtefact.objects.filter(consent_request__user=self.request.user).order_by(
            '-date_created')
        if self.action == 'list':
            request_params = self.request.query_params
            if not request_params.get('consent_request_id'):
                raise ValidationError(detail={'consent_request_id': ERROR_CODE_REQUIRED_MESSAGE},
                                      code=ERROR_CODE_REQUIRED)
            queryset = queryset.filter(consent_request=request_params['consent_request_id'])
            if request_params.get('search'):
                queryset = queryset.filter(details__hip__name__icontains=request_params['search'])
        return queryset
