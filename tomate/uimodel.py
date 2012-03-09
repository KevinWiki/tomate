# -*- coding: utf-8 -*-

# Copyright 2012 Jerry Peng
#
# Tomate is a time management tool inspired by the
# pomodoro technique(http://www.pomodorotechnique.com/).
#
# Tomate is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option
# any later version.
#
# Tomate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with Foobar. If not, see http://www.gnu.org/licenses/.


import pygtk
pygtk.require('2.0')
import gtk
import gobject
import itertools

from datetime import datetime
from datetime import time
from datetime import timedelta

from tomate import model

class ActivityStore(gtk.ListStore):

    (TITLE_COL,
     FINISHED_COL,
     TOMATO_COL,
     INTERRUPT_COL,
     ACTIVITY_COL) = range(5)

    def __init__(self, priority=model.TODO, store=None):
        super(ActivityStore, self).__init__(str, bool, int, int, gobject.TYPE_PYOBJECT)
        self.priority = priority
        if not store:
            store = model.open_store()
        self.store = store

    def _append_activity(self, act):
        self.append([act.name,
                     act.finish_time is not None,
                     act.tomatoes,
                     act.interrupts,
                     act])

    def _update_activity(self, act, it):
        self.set_value(it, self.TITLE_COL, act.name)
        self.set_value(it, self.FINISHED_COL, act.finish_time is not None)
        self.set_value(it, self.TOMATO_COL, act.tomatoes)
        self.set_value(it, self.INTERRUPT_COL, act.interrupts)

    def load_activities(self):
        acts = self.store.list_activities(priority=self.priority)
        self.clear()
        for act in acts:
            self._append_activity(act)

    def add_activity(self, act):
        #Make sure the activity has the same priority with current model's
        act.priority = self.priority
        self.store.save_activity(act)
        self._append_activity(act)

    def get_activity_byiter(self, it):
        activity = self.get_value(it, self.ACTIVITY_COL)
        activity._path = self.get_path(it)
        return activity

    def get_activity_bypath(self, path):
        activity = self[path][self.ACTIVITY_COL]
        activity._path = path
        return activity

    def delete_activity_byiter(self, it):
        activity = self.get_value(it, self.ACTIVITY_COL)
        self.store.delete_activity(activity)
        self.remove(it)

    def update_activity(self, act):
        self.store.update_activity(act)
        it = self.get_iter(act._path)
        if act.priority == self.priority:
            self._update_activity(act, it)
        else:
            self.remove(it)

    def finish_tomato(self, tomato, interrupt):
        if interrupt:
            tomato.interrupt()
        else:
            tomato.finish()
        self.update_activity(tomato.activity)
        self.store.save_tomato(tomato)

    def close(self):
        self.store.archive_activities()
        self.store.close()


def day_range(date):
    t = time(0, 0, 0)
    start_time = datetime.combine(date, t)
    end_time = start_time + timedelta(days=1)
    return (start_time, end_time)


class FinishedTomatoModel(gtk.ListStore):
    (TIME_COL,
     ACTIVITY_COL,
     INTERRUPTED_COL) = range(3)

    def __init__(self, store=None):
        super(FinishedTomatoModel, self).__init__(str, str, bool)
        if not store:
            store = model.open_store()
        self.store = store

    def load_finished_tomatoes(self, date):
        start_time, end_time = day_range(date)
        tomatoes = self.store.list_tomatoes(start_time, end_time)
        self.clear()
        interrupt_count = 0
        for tomato in tomatoes:
            start = datetime.fromtimestamp(tomato.start_time).strftime('%H:%M')
            end = datetime.fromtimestamp(tomato.end_time).strftime('%H:%M')
            interrupt = (tomato.state == model.INTERRUPTED)
            if interrupt:
                interrupt_count = interrupt_count + 1
            self.append(('%s - %s' % (start, end), tomato.name, interrupt))
        return (len(tomatoes) - interrupt_count, interrupt_count)


class FinishedActivityModel(gtk.ListStore):
    """List model for Activity history"""
    def __init__(self, store=None):
        super(FinishedActivityModel, self).__init__(bool, str)
        if not store:
            store = model.open_store()
        self.store = store

    def load_finished_activities(self, date):
        start_time, end_time = day_range(date)
        act_histories = self.store.list_activity_histories(start_time, end_time)
        acts = self.store.list_finished_activities(start_time, end_time)
        self.clear()
        for act in itertools.chain(act_histories, acts):
            self.append((True, act.name))
        return len(act_histories) + len(acts)


class WeeklyStatisticsModel(gobject.GObject):
    """Weekly statistics model"""

    __gsignals__ = {
            'data-updated' : (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE, (int,))
            }

    WEEKDAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

    def __init__(self, store=None):
        super(WeeklyStatisticsModel, self).__init__()
        if not store:
            store = model.open_store()
        self.store = store
        self.data = []
        self.cache_day = None

    def get_data(self):
        return self.data

    def reload_data(self, date, force=False):
        weekday = date.weekday()
        start_day = date - timedelta(days=weekday)
        if force or start_day != self.cache_day:
            end_day = date + timedelta(days=6-weekday-1)
            start_time = datetime.combine(start_day, time(0, 0, 0))
            end_time = datetime.combine(end_day, time(23, 59, 59))
            data = self.store.statistics_tomato_count(start_time, end_time)
            self.data = [(self.WEEKDAY_NAMES[datetime.fromtimestamp(t).weekday()], d)
                    for t, d in data]
            self.cache_day = start_day
        self.emit('data-updated', weekday)

