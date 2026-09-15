from rest_framework import serializers
from .models import TypeDechet, ConseilTri


class ConseilTriSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConseilTri
        fields = ['idConseil', 'consigne', 'idTypeDechet']


class TypeDechetSerializer(serializers.ModelSerializer):
    # Inclut le conseil de tri directement dans la réponse (relation 1-1)
    conseil = ConseilTriSerializer(read_only=True)

    class Meta:
        model = TypeDechet
        fields = ['idTypeDechet', 'nom', 'description', 'conseil']