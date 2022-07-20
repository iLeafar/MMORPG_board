from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, DetailView, DeleteView, UpdateView

from .filter import NoteFilter, ResponseFilter
from .forms import NoteForm, ResponseForm
from .models import *


class NoteMain(ListView):
    """Главная страница, вывод в виде списка всех объявлений"""
    model = Note
    template_name = 'main.html'
    context_object_name = 'notes'
    ordering = ['-datetime']
    paginate_by = 5


class NoteCreate(CreateView):
    """Создание нового объявления"""
    template_name = 'note_create.html'
    form_class = NoteForm

    def form_valid(self, form):
        """Автозаполнение поля user"""
        form.instance.user = self.request.user
        return super().form_valid(form)


class NoteDelete(DeleteView):
    """Удаление объявления"""
    template_name = 'note_delete.html'
    # queryset - переопределение вывода информации на страницу
    queryset = Note.objects.all()
    # success_url - перенаправление на url с name = 'main'
    success_url = reverse_lazy('main')


class NoteDetail(DetailView):
    """Вывод подробностей объявления"""
    template_name = 'note_detail.html'
    queryset = Note.objects.all()
    form = ResponseForm
    # простой вариант добавления переменной в шаблон
    extra_context = {'form': ResponseForm}

    def get_context_data(self, **kwargs):
        """Функция для видимости поля откликов, поле не видимо если:
        1) я - автор объявления (самому себе отклик отправлять не нужно)
        2) уже отправил отклик на объявление ранее (два раза нельзя отправлять отклик на одно
        и тоже объявление, от спама и прочего)"""
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')
        note_author = Note.objects.get(id=pk).user
        current_user = self.request.user

        # проверка на то, что ты - зарегистрированный пользователь
        if current_user.is_authenticated:
            # если ты автор объявления, то скрыть поле ввода отклика
            if note_author == self.request.user:
                context['pole_response'] = False
                context['message_response'] = False
                context['edit_delete'] = True
            # если ты уже ранее сделал отклик - поле отклика скрыть
            elif Response.objects.filter(user_response=self.request.user).filter(note=pk).exists():
                context['pole_response'] = False
                context['message_response'] = True
                context['edit_delete'] = False
            # если ты не автор объявления, и не сделал отклик ранее - поле видимо
            else:
                context['pole_response'] = True
                context['message_response'] = False
                context['edit_delete'] = False

        return context

    def post(self, request, *args, **kwargs):
        """При отправки формы выполнить следующий код
        form.instance - для автоматического заполнения (переопределения) полей формы
        instance - типа данный объект, вроде self, но со своими особенностями"""
        form = ResponseForm(request.POST)
        if form.is_valid():
            form.instance.note_id = self.kwargs.get('pk')
            form.instance.user_response = self.request.user
            form.save()

            # волшебная ссылка перехода на ту же самую страницу после
            # выполнения POST-запроса, хвала stackoverflow.com
            return redirect(request.META.get('HTTP_REFERER'))


class NoteEdit(UpdateView):
    """Редактирование объявления"""
    template_name = 'note_edit.html'
    form_class = NoteForm

    def get_object(self, **kwargs):
        """Помогает получить нужный объект и вывести его на страницу"""
        pk = self.kwargs.get('pk')
        return Note.objects.get(pk=pk)


class NoteSearch(ListView):
    """Фильтр и поиск объявлений"""
    model = Note
    template_name = 'note_search.html'
    context_object_name = 'note'
    ordering = ['-datetime']

    def get_context_data(self, **kwargs):
        """Для добавления новой переменной на страницу (filter)"""
        context = super().get_context_data(**kwargs)
        context['filter'] = NoteFilter(self.request.GET, queryset=self.get_queryset())
        return context


class ResponseList(ListView):
    """Страница откликов пользователя
    выводит не наши отклики, а отклики на наши объявления"""
    template_name = 'user_response.html'
    context_object_name = 'responses'
    ordering = ['-datetime']

    def get_queryset(self, **kwargs):
        """Создает фильтры для вывода нужных объектов, 1 фильтр - по текущему пользователю
        то есть выводятся объявления только текущего пользователя, 2,3 фильтры - по статусу
        то есть еще не отклоненные/не принятые ранее отклики"""
        user_id = self.request.user.id
        return Response.objects.filter(note__user=user_id).filter(status_del=False).filter(status_add=False)

    def get_context_data(self, **kwargs):
        """Для добавления новых переменных на страницу
        filter - фильтрует отклики по объявлениям (форма выбора на странице)
        del_response - выводит отклоненные отклики (так, для удобства)
        add_response - выводит принятые отклики (так, для удобства)"""
        context = super().get_context_data(**kwargs)
        user_id = self.request.user.id
        context['filter'] = ResponseFilter(self.request.GET, queryset=self.get_queryset())
        context['new_response'] = Response.objects. \
            filter(note__user=user_id).filter(status_del=False).filter(status_add=False)
        context['del_response'] = Response.objects.filter(note__user=user_id).filter(status_del=True)
        context['add_response'] = Response.objects.filter(note__user=user_id).filter(status_add=True)
        return context


class ResponseAccept(View):
    """Принятие отклика"""

    def get(self, request, *args, **kwargs):
        """Присваивает полю status_add значение = 1, то есть True, означает, что отклик
        принят, то есть он остается в бд, но больше не отображается в списке новых откликов"""
        pk = self.kwargs.get('pk')
        resp = Response.objects.get(pk=pk)
        resp.status_add = 1
        resp.status_del = 0
        resp.save()

        return redirect('response')


class ResponseRemove(View):
    """Отклонение (условное удаление) отклика"""

    def get(self, request, *args, **kwargs):
        """Присваивает полю status_del значение = 1, то есть True, означает, что отклик
        отклонен, то есть он остается в бд, но больше не отображается в списке новых откликов"""
        pk = self.kwargs.get('pk')
        qaz = Response.objects.get(id=pk)
        qaz.status_del = 1
        qaz.status_add = 0
        qaz.save()

        return redirect('response')


# блокировка представлений от действий незарегистрированных пользователей

class ProtectNoteCreate(LoginRequiredMixin, NoteCreate):
    permission_required = ('create',)


class ProtectNoteDelete(LoginRequiredMixin, NoteDelete):
    permission_required = ('delete',)


class ProtectNoteEdit(LoginRequiredMixin, NoteEdit):
    permission_required = ('edit',)


class ProtectResponseList(LoginRequiredMixin, ResponseList):
    permission_required = ('response',)


class ProtectResponseAccept(LoginRequiredMixin, ResponseAccept):
    permission_required = ('accept',)


class ProtectResponseRemove(LoginRequiredMixin, ResponseRemove):
    permission_required = ('remove',)