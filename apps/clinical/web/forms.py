from django import forms


class DentalExamForm(forms.Form):
    patient_id = forms.IntegerField()
    company_id = forms.IntegerField(required=False)
    additional_notes = forms.CharField(required=False, widget=forms.Textarea)
    tooth_loss_classification = forms.CharField(required=False)
    other_oral_conditions = forms.CharField(required=False, widget=forms.Textarea)
    chewing_ability = forms.CharField(required=False)
    health_classification = forms.CharField(required=False)
    conclusion = forms.CharField(required=False, widget=forms.Textarea)


class PathologyUploadForm(forms.Form):
    patient_id = forms.IntegerField()
    pdf_file = forms.FileField()
    location = forms.CharField(required=False)
    result_date = forms.DateField(input_formats=["%Y-%m-%d"])
    manual_conclusion = forms.CharField(required=False, widget=forms.Textarea)


class PathologyEvaluationForm(forms.Form):
    result_id = forms.IntegerField()
    evaluation = forms.CharField(required=False)