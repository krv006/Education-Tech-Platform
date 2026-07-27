from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Consent, ParentChildLink, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'role', 'phone', 'invite_code']
        read_only_fields = ['role', 'invite_code']


class RegisterSerializer(serializers.ModelSerializer):
    """Public registration — only teacher or parent. Students are created by a parent."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    role = serializers.ChoiceField(choices=[User.Role.TEACHER, User.Role.PARENT])

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'role', 'phone']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChildCreateSerializer(serializers.ModelSerializer):
    """Parent creates a child account; the link is approved immediately (FRD: auth.child_create)."""

    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'invite_code']
        read_only_fields = ['invite_code']

    def create(self, validated_data):
        password = validated_data.pop('password')
        child = User(role=User.Role.STUDENT, **validated_data)
        child.set_password(password)
        child.save()
        ParentChildLink.objects.create(
            parent=self.context['request'].user,
            student=child,
            status=ParentChildLink.Status.APPROVED,
        )
        return child


class LinkSerializer(serializers.ModelSerializer):
    parent = UserSerializer(read_only=True)
    student = UserSerializer(read_only=True)

    class Meta:
        model = ParentChildLink
        fields = ['id', 'parent', 'student', 'status', 'created_at', 'responded_at']


class LinkRequestSerializer(serializers.Serializer):
    invite_code = serializers.CharField(max_length=12)

    def validate_invite_code(self, value):
        try:
            self.student = User.objects.get(invite_code=value.strip().upper(), role=User.Role.STUDENT)
        except User.DoesNotExist:
            raise serializers.ValidationError("Bunday taklif kodi topilmadi.")
        return value


class LinkRespondSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'decline'])


class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consent
        fields = ['id', 'student', 'kind', 'granted', 'updated_at']
        read_only_fields = ['updated_at']
