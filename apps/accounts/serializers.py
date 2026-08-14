from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Consent, ParentChildLink, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'role', 'phone', 'invite_code', 'avatar']
        read_only_fields = ['role', 'invite_code']


class RegisterSerializer(serializers.ModelSerializer):
    """Ochiq ro'yxatdan o'tish — faqat o'qituvchi yoki ota-ona (bola hisobini ota-ona ochadi)."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    role = serializers.ChoiceField(choices=[User.Role.TEACHER, User.Role.PARENT])

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'role', 'phone']


class ChildCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'invite_code']
        read_only_fields = ['invite_code']


class LinkSerializer(serializers.ModelSerializer):
    parent = UserSerializer(read_only=True)
    student = UserSerializer(read_only=True)

    class Meta:
        model = ParentChildLink
        fields = ['id', 'parent', 'student', 'status', 'created_at', 'responded_at']


class LinkRequestSerializer(serializers.Serializer):
    invite_code = serializers.CharField(max_length=12)


class LinkRespondSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'decline'])


class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consent
        fields = ['id', 'student', 'kind', 'granted', 'updated_at']
        read_only_fields = ['updated_at']
