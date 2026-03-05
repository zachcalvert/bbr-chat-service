from django.shortcuts import get_object_or_404, render

from .models import VoiceMember


def member_list(request):
    """List all active voice members."""
    members = VoiceMember.objects.filter(is_active=True)
    return render(request, 'voice/member_list.html', {'members': members})


def member_detail(request, pk):
    """View a voice member with sample messages."""
    member = get_object_or_404(VoiceMember, pk=pk)
    sample_messages = member.messages.order_by('?')[:20]
    return render(request, 'voice/member_detail.html', {
        'member': member,
        'sample_messages': sample_messages,
    })
