from abc import ABC

from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from rest_framework import exceptions
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken

from demo_project.utility import check_email_or_phone, check_user_type
from shared.utils import phone_parser, send_email, send_phone_notification
from users.models import User, UserConfirmation, VIA_EMAIL, VIA_PHONE, CODE_VERIFIED, DONE, NEW


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):

    def __init__(self, *args, **kwargs):
        super(MyTokenObtainPairSerializer, self).__init__(*args, **kwargs)
        self.fields['userinput'] = serializers.CharField(required=False)
        self.fields['username'] = serializers.CharField(read_only=True, required=False)

    def auth_validate(self, attrs):
        print(attrs)
        user_input = attrs.get('userinput')
        print(user_input)
        if check_user_type(user_input) == "username":
            username = attrs.get('userinput')
        elif check_user_type(user_input) == "email":
            user = self.get_user(email__iexact=user_input)
            username = user.username
        elif check_user_type(user_input) == "phone":
            user = self.get_user(phone_number=user_input)
            username = user.username
        else:
            data = {
                'success': False,
                'message': "You must send username or email or phone_number"
            }
            return ValidationError(data)
        authentication_kwargs = {
            self.username_field: username,
            'password': attrs['password']
        }
        print(authentication_kwargs)
        current_user = User.objects.filter(username__iexact=username).first()
        if current_user.auth_status != DONE:
            raise ValidationError({"message": "You didn't complete your authentication process. Auth_status error"})
        user = authenticate(**authentication_kwargs)
        if user is not None:
            self.user = user
        else:
            raise ValidationError(
                {"password": "Sorry, login or password you entered is incorrect. Please check and try again."}
            )

    def validate(self, attrs):
        self.auth_validate(attrs)
        if self.user.auth_status != DONE:
            raise PermissionDenied("You can't access to the program")
        data = self.user.tokens()
        data['auth_status'] = self.user.auth_status
        return data

    def get_user(self, **kwargs):
        users = User.objects.filter(**kwargs)
        if not users.exists():
            raise exceptions.AuthenticationFailed(
                self.error_messages['no_active_account'],
                "no_active_account",
            )
        return users.first()


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        access_token_instance = AccessToken(data['access'])
        user_id = access_token_instance['user_id']
        user = get_object_or_404(User, id=user_id)
        update_last_login(None, user)
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class SignUpSerializer(serializers.ModelSerializer):
    guid = serializers.UUIDField(read_only=True)

    def __init__(self, *args, **kwargs):
        super(SignUpSerializer, self).__init__(*args, **kwargs)
        self.fields['email_phone_number'] = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = (
            "guid",
            "auth_type",
            "auth_status"
        )
        extra_kwargs = {
            'auth_type': {'read_only': True, 'required': False},
            'auth_status': {'read_only': True, 'required': False}
        }

    def create(self, validated_data):
        user = super(SignUpSerializer, self).create(validated_data)
        print(user)
        if user.auth_type == VIA_EMAIL:
            code = user.create_verify_code(user.auth_type)
            print(code)
            send_email(user.email, code)
            print("email sending..")
        elif user.auth_type == VIA_PHONE:
            code = user.create_verify_code(user.auth_type)
            send_email(user.email, code)
            # send_phone_notification(user.phone_number, code)
        user.save()
        return user

    def validate(self, attrs):
        super(SignUpSerializer, self).validate(attrs)
        data = self.auth_validate(attrs)
        return data

    @staticmethod
    def auth_validate(attrs):
        user_input = str(attrs.get('email_phone_number')).lower()
        print(user_input)
        input_type = check_email_or_phone(user_input)
        if input_type == "email":
            data = {
                "email": attrs.get('email_phone_number'),
                'auth_type': VIA_EMAIL
            }
        elif input_type == "phone":
            data = {
                "phone_number": attrs.get('email_phone_number'),
                'auth_type': VIA_PHONE
            }
        elif input_type is None:
            data = {
                'success': False,
                'message': "You must send email or phone number"
            }
            raise ValidationError(data)
        else:
            data = {
                'success': False,
                'message': "Must send email or phone number"
            }
            raise ValidationError(data)
        # data.update(password=attrs.get('password'))
        return data

    def validate_email_phone_number(self, value): # value = "samandar@gmail.com"
        value = value.lower()
        query = (Q(phone_number=value) | Q(email=value)) & (
            Q(auth_status=NEW) | Q(auth_status=CODE_VERIFIED)
        )
        print(query)
        if User.objects.filter(query).exists():
            print('topildi')
            User.objects.get(query).delete()

        if value and User.objects.filter(email=value).exists():
            data = {
                "success": False,
                "message": "This Email address is already being used!"
            }
            raise ValidationError(data)

        elif value and User.objects.filter(phone_number=value).exists():
            data = {
                "success": False,
                "message": "This phone number is already being used!"
            }
            raise ValidationError(data)

        if check_email_or_phone(value) == "phone": # 998981234555
            phone_parser(value, self.initial_data.get("country_code"))
        return value

    def to_representation(self, instance):
        data = super(SignUpSerializer, self).to_representation(instance)
        data.update(instance.tokens())
        return data


class ChangeUserInformationSerializer(serializers.Serializer):
    bio = serializers.CharField(write_only=True, required=True)
    sex = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(write_only=True, required=True)
    username = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate_bio(self, bio):
        if bio and len(bio) > 250:
            raise ValidationError("Bio can not be more than 250 characters")
        return bio

    def validate_password(self, password):
        validate_password(password)
        return password

    def validate_username(self, username):
        requested_user = self.context['request'].user
        user_name = requested_user.username
        if len(username) < 5 or len(username) > 30:
            raise ValidationError("Username must be between 5 and 30 characters long")
        if username.isdigit():
            raise ValidationError("This username is entirely numeric.")
        if User.objects.filter(username__iexact=username).exclude(username=user_name).exists():
            raise ValidationError("This username is already exists")

        return username

    def validate(self, data):
        print(data)
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        if password:
            validate_password(password)
            validate_password(confirm_password)
        if password != confirm_password:
            raise ValidationError("Your passwords don't match")

        return data

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.username = validated_data.get('username', instance.username)
        instance.password = validated_data.get('password', instance.password)
        instance.bio = validated_data.get('bio', instance.bio)
        instance.sex = validated_data.get('sex', instance.sex)

        if validated_data.get('password'):
            instance.set_password(validated_data.get('password'))

        if instance.auth_status == CODE_VERIFIED:
            user = self.context['request'].user
            user.auth_status = DONE
            user.save()
        instance.save()
        return instance
