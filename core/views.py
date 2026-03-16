from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from .exceptions import CustomAPIException


class BaseAPIView(APIView):
    """
    Base API view with standard response formatting.
    """
    
    def handle_exception(self, exc):
        if isinstance(exc, CustomAPIException):
            return Response(
                {
                    'success': False,
                    'error': exc.detail,
                    'code': exc.get_codes()
                },
                status=exc.status_code
            )
        return super().handle_exception(exc)

    def success_response(self, data=None, message='Success', status_code=status.HTTP_200_OK):
        return Response(
            {
                'success': True,
                'message': message,
                'data': data
            },
            status=status_code
        )

    def error_response(self, message='Error', errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        return Response(
            {
                'success': False,
                'message': message,
                'errors': errors
            },
            status=status_code
        )


class BaseViewSet(ModelViewSet):
    """
    Base ViewSet with common configurations.
    """
    def success_response(self, data=None, message="Success", status_code=200):
        from rest_framework.response import Response
        return Response({"success": True, "message": message, "data": data}, status=status_code)

    def error_response(self, message="Error", status_code=400):
        from rest_framework.response import Response
        return Response({"success": False, "message": message}, status=status_code)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                'success': True,
                'message': 'Created successfully',
                'data': serializer.data
            },
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(
            {
                'success': True,
                'message': 'Updated successfully',
                'data': serializer.data
            }
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {
                'success': True,
                'message': 'Deleted successfully'
            },
            status=status.HTTP_204_NO_CONTENT
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                'success': True,
                'data': serializer.data
            }
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(
            {
                'success': True,
                'data': serializer.data
            }
        )