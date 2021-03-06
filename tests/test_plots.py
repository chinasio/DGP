# -*- coding: utf-8 -*-
from datetime import datetime

import pytest
import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject
from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import QWidget
from pyqtgraph import GraphicsLayout, PlotItem, PlotDataItem, LegendItem

from dgp.core.oid import OID
from dgp.gui.plotting.backends import GridPlotWidget, Axis, AxisFormatter
from dgp.gui.plotting.plotters import LineSelectPlot
from dgp.gui.plotting.helpers import PolyAxis, LinearSegment, LinearSegmentGroup, LineUpdate

"""Test/Develop Plots using PyQtGraph for high-performance user-interactive 
plots within the application.

"""


@pytest.fixture
def gravity(gravdata) -> pd.Series:
    return gravdata['gravity']


def test_GridPlotWidget_init():
    gpw = GridPlotWidget(rows=2)
    assert isinstance(gpw, QWidget)
    assert isinstance(gpw, QObject)

    assert isinstance(gpw.centralWidget, GraphicsLayout)

    assert 2 == gpw.rows
    assert 1 == gpw.cols

    assert isinstance(gpw.get_plot(row=0), PlotItem)
    assert isinstance(gpw.get_plot(row=1), PlotItem)
    assert gpw.get_plot(row=2) is None

    p0 = gpw.get_plot(row=0)
    assert isinstance(p0.legend, LegendItem)


def test_GridPlotWidget_make_index(gravdata):
    assert ('gravity', 0, 1, Axis.LEFT) == GridPlotWidget.make_index(gravdata['gravity'].name, 0, 1)

    unnamed_ser = pd.Series(np.zeros(14), name='')
    with pytest.raises(ValueError):
        GridPlotWidget.make_index(unnamed_ser.name, 1, 1)

    upper_ser = pd.Series(np.zeros(14), name='GraVitY')
    assert ('gravity', 2, 0, Axis.LEFT) == GridPlotWidget.make_index(upper_ser.name, 2, 0)

    assert ('long_acc', 3, 1, Axis.LEFT) == GridPlotWidget.make_index('long_acc', 3, 1, 'sideways')


def test_GridPlotWidget_add_series(gravity):
    gpw = GridPlotWidget(rows=2)
    p0: PlotItem = gpw.get_plot(row=0)
    p1: PlotItem = gpw.get_plot(row=1)

    assert 0 == len(p0.dataItems) == len(p1.dataItems)

    assert 'gravity' == gravity.name
    assert isinstance(gravity, pd.Series)

    # Plotting an item should return a reference to the PlotDataItem
    _grav_item0 = gpw.add_series(gravity, row=0)
    assert 1 == len(p0.items)
    assert gravity.equals(gpw.get_series(gravity.name, row=0))
    assert isinstance(_grav_item0, PlotDataItem)
    assert gravity.name in [label.text for _, label in p0.legend.items]

    # Re-plotting an existing series on the same plot should do nothing
    _items_len = len(list(gpw._items.values()))
    gpw.add_series(gravity, row=0)
    assert 1 == len(p0.dataItems)
    assert _items_len == len(list(gpw._items.values()))

    # Allow plotting of a duplicate series to a second plot
    _items_len = len(list(gpw._items.values()))
    gpw.add_series(gravity, row=1)
    assert 1 == len(p1.dataItems)
    assert _items_len + 1 == len(list(gpw._items.values()))

    # Remove series only by name (assuming it can only ever be plotted once)
    # or specify which plot to remove it from?
    gpw.remove_series(gravity.name, row=0)
    assert 0 == len(p0.dataItems)
    key = 0, 0, gravity.name
    assert gpw._series.get(key, None) is None
    assert gpw._items.get(key, None) is None
    assert 'gravity' not in [label.text for _, label in p0.legend.items]

    with pytest.raises(KeyError):
        gpw.remove_series('eotvos', 0, 0)


def test_GridPlotWidget_remove_series(gravity):
    gpw = GridPlotWidget(rows=3, multiy=True)
    p0 = gpw.get_plot(row=0)
    p0right = gpw.get_plot(row=0, axis=Axis.RIGHT)
    p1 = gpw.get_plot(row=1)
    p2 = gpw.get_plot(row=2)

    assert 0 == len(p0.dataItems) == len(p1.dataItems) == len(p2.dataItems)
    _grav0 = gpw.add_series(gravity, row=0, axis=Axis.LEFT)
    _grav1 = gpw.add_series(gravity, row=0, axis=Axis.RIGHT)

    assert 1 == len(p0.dataItems) == len(p0right.dataItems)

    gpw.remove_series(gravity.name, 0, axis=Axis.LEFT)
    assert 0 == len(p0.dataItems)
    assert 1 == len(p0right.dataItems)
    gpw.remove_series(gravity.name, 0, axis=Axis.RIGHT)
    assert 0 == len(p0right.dataItems)


def test_GridPlotWidget_remove_plotitem(gravity):
    gpw = GridPlotWidget(rows=2)
    p0 = gpw.get_plot(0)
    p1 = gpw.get_plot(1)

    _grav_item0 = gpw.add_series(gravity, 0)
    _grav_item1 = gpw.add_series(gravity, 1)
    assert 1 == len(p0.dataItems) == len(p1.dataItems)
    assert _grav_item0 in p0.dataItems
    assert _grav_item0 in gpw._items.values()

    gpw.remove_plotitem(_grav_item0)
    assert 0 == len(p0.dataItems)
    assert 1 == len(p1.dataItems)
    assert _grav_item0 not in gpw._items.items()
    assert _grav_item0 not in p0.dataItems
    assert gpw._series.get((0, 0, 'gravity'), None) is None

    assert 'gravity' not in [label.text for _, label in p0.legend.items]


def test_GridPlotWidget_find_series(gravity):
    """Test function to find & return all keys for a series identified by name
    e.g. if 'gravity' channel is plotted on plot rows 0 and 1, find_series
    should return a list of key tuples (row, col, name) where the series is
    plotted.
    """
    gpw = GridPlotWidget(rows=3)
    assert 3 == gpw.rows

    gpw.add_series(gravity, 0)
    gpw.add_series(gravity, 2)

    expected = [(gravity.name, 0, 0, Axis.LEFT), (gravity.name, 2, 0, Axis.LEFT)]
    result = gpw.find_series(gravity.name)
    assert expected == result

    _grav_series0 = gpw.get_series(*result[0])
    assert gravity.equals(_grav_series0)


def test_GridPlotWidget_set_xaxis_formatter(gravity):
    """Test that appropriate axis formatters are automatically added based on
    the series index type (numeric or DateTime)
    """
    gpw = GridPlotWidget(rows=2)
    gpw.add_series(gravity, 1)

    p0 = gpw.get_plot(0)
    btm_axis_p0 = p0.getAxis('bottom')
    gpw.set_xaxis_formatter(formatter=AxisFormatter.DATETIME, row=0)
    assert isinstance(btm_axis_p0, PolyAxis)
    assert btm_axis_p0.timeaxis

    p1 = gpw.get_plot(1)
    btm_axis_p1 = p1.getAxis('bottom')
    assert isinstance(btm_axis_p1, PolyAxis)
    assert not btm_axis_p1.timeaxis

    gpw.set_xaxis_formatter(formatter=AxisFormatter.SCALAR, row=0)
    assert not p0.getAxis('bottom').timeaxis


def test_GridPlotWidget_sharex(gravity):
    """Test linked vs unlinked x-axis scales"""
    gpw_unlinked = GridPlotWidget(rows=2, sharex=False)

    gpw_unlinked.add_series(gravity, 0, autorange=False)
    up0_xlim = gpw_unlinked.get_xlim(row=0)
    up1_xlim = gpw_unlinked.get_xlim(row=1)

    assert up1_xlim == [0, 1]
    assert up0_xlim != up1_xlim
    gpw_unlinked.set_xlink(True)
    assert gpw_unlinked.get_xlim(row=0) == gpw_unlinked.get_xlim(row=1)
    gpw_unlinked.set_xlink(False, autorange=True)
    gpw_unlinked.add_series(pd.Series(np.random.rand(len(gravity)),
                                      name='rand'), 1)
    assert gpw_unlinked.get_xlim(row=0) != gpw_unlinked.get_xlim(row=1)

    gpw_linked = GridPlotWidget(rows=2, sharex=True)
    gpw_linked.add_series(gravity, 0)
    assert gpw_linked.get_xlim(row=0) == gpw_linked.get_xlim(row=1)


def test_GridPlotWidget_iterator():
    """Test plots generator property for iterating through all plots"""
    gpw = GridPlotWidget(rows=5)
    count = 0
    for i, plot in enumerate(gpw.plots):
        assert isinstance(plot, PlotItem)
        plot_i = gpw.get_plot(i, 0)
        assert plot_i == plot
        count += 1

    assert gpw.rows == count


def test_GridPlotWidget_clear(gravdata):
    """Test clearing all series from all plots, or selectively"""
    gpw = GridPlotWidget(rows=3)
    gpw.add_series(gravdata['gravity'], 0)
    gpw.add_series(gravdata['long_accel'], 1)
    gpw.add_series(gravdata['cross_accel'], 2)

    assert 3 == len(gpw._items)
    p0 = gpw.get_plot(0, 0)
    assert 1 == len(p0.dataItems)

    gpw.clear()

    assert 0 == len(gpw._items)
    assert 0 == len(p0.dataItems)

    # TODO: Selective clear not yet implemented


def test_GridPlotWidget_multi_y(gravdata):
    _gravity = gravdata['gravity']
    _longacc = gravdata['long_accel']
    gpw = GridPlotWidget(rows=1, multiy=True)

    p0 = gpw.get_plot(0)
    gpw.add_series(_gravity, 0)
    gpw.add_series(_longacc, 0, axis=Axis.RIGHT)

    # Legend entry for right axis should appear on p0 legend
    assert _gravity.name in [label.text for _, label in p0.legend.items]
    assert _longacc.name in [label.text for _, label in p0.legend.items]

    assert 1 == len(gpw.get_plot(0).dataItems)
    assert 1 == len(gpw.get_plot(0, axis=Axis.RIGHT).dataItems)

    assert gpw.get_xlim(0) == gpw.get_plot(0, axis=Axis.RIGHT).vb.viewRange()[0]


@pytest.mark.skip
@pytest.mark.parametrize("delta,expected", [
    (pd.Timedelta(seconds=1), [(pd.Timedelta(milliseconds=100).value, 0)]),
    (pd.Timedelta(seconds=2), [(pd.Timedelta(milliseconds=333).value, 0)]),
    (pd.Timedelta(seconds=60), [(pd.Timedelta(seconds=10).value, 0)]),
    (pd.Timedelta(seconds=1200), [(pd.Timedelta(seconds=15*60).value, 0)]),
])
def test_PolyAxis_dateTickSpacing_major(delta, expected):
    """Test generation of tick spacing tuples for a PolyAxis in date mode.

    The tickSpacing method accepts a minVal, maxVal and size parameter

    size is the pixel length/width of the axis where the ticks will be displayed

    """
    axis = PolyAxis(orientation='bottom', timeaxis=True)
    assert axis.timeaxis

    _size = 600

    t0: pd.Timestamp = pd.Timestamp.now()
    t1: pd.Timestamp = t0 + delta

    assert expected == axis.dateTickSpacing(t0.value, t1.value, _size)


@pytest.mark.skip
def test_PolyAxis_tickStrings():
    axis = PolyAxis(orientation='bottom')
    axis.timeaxis = True
    _scale = 1.0
    _spacing = pd.Timedelta(seconds=1).value

    _HOUR_SEC = 3600
    _DAY_SEC = 86400

    dt_index = pd.DatetimeIndex(start=datetime(2018, 6, 15, 12, 0, 0), freq='s',
                                periods=8 * _DAY_SEC)
    dt_list = pd.to_numeric(dt_index).tolist()

    # Test with no values passed
    assert [] == axis.tickStrings([], _scale, 1)

    # If the plot range is <= 60 seconds, ticks should be formatted as %M:%S
    _minute = 61
    expected = [pd.to_datetime(dt_list[i]).strftime('%M:%S') for i in range(_minute)]
    assert expected[1:] == axis.tickStrings(dt_list[:_minute], _scale, _spacing)[1:]

    # If 1 minute < plot range <= 1 hour, ticks should be formatted as %H:%M
    _hour = 60 * 60 + 1
    expected = [pd.to_datetime(dt_list[i]).strftime('%H:%M') for i in range(0, _hour, 5)]
    assert expected[1:] == axis.tickStrings(dt_list[:_hour:5], _scale, _spacing)[1:]

    # If 1 hour < plot range <= 1 day, ticks should be formatted as %d %H:%M
    tick_values = [dt_list[i] for i in range(0, 23 * _HOUR_SEC, _HOUR_SEC)]
    expected = [pd.to_datetime(v).strftime('%d %H:%M') for v in tick_values]
    assert expected == axis.tickStrings(tick_values, _scale, _HOUR_SEC)

    # If 1 day < plot range <= 1 week, ticks should be formatted as %m-%d %H

    tick_values = [dt_list[i] for i in range(0, 3 * _DAY_SEC, _DAY_SEC)]
    expected = [pd.to_datetime(v).strftime('%m-%d %H') for v in tick_values]
    assert expected == axis.tickStrings(tick_values, _scale, _DAY_SEC)


def test_LineSelectPlot_init():
    plot = LineSelectPlot(rows=2)

    assert isinstance(plot, QObject)
    assert isinstance(plot, QWidget)

    assert 2 == plot.rows


def test_LineSelectPlot_selection_mode():
    plot = LineSelectPlot(rows=3)
    assert not plot.selection_mode
    plot.set_select_mode(True)
    assert plot.selection_mode

    plot.add_segment(datetime.now().timestamp(),
                     datetime.now().timestamp() + 1000)

    assert 1 == len(plot._segments)

    for lfr_grp in plot._segments.values():  # type: LinearSegmentGroup
        assert lfr_grp.movable

    plot.set_select_mode(False)
    for lfr_grp in plot._segments.values():
        assert not lfr_grp.movable


def test_LineSelectPlot_add_segment():
    _rows = 2
    plot = LineSelectPlot(rows=_rows)
    update_spy = QSignalSpy(plot.sigSegmentChanged)

    ts_oid = OID(tag='datetime_timestamp')
    ts_start = datetime.now().timestamp() - 1000
    ts_stop = ts_start + 200

    pd_oid = OID(tag='pandas_timestamp')
    pd_start = pd.Timestamp.now()
    pd_stop = pd_start + pd.Timedelta(seconds=1000)

    assert 0 == len(plot._segments)

    plot.add_segment(ts_start, ts_stop, uid=ts_oid)
    assert 1 == len(update_spy)
    assert 1 == len(plot._segments)
    lfr_grp = plot._segments[ts_oid]
    assert _rows == len(lfr_grp._segments)

    # Test adding segment using pandas.Timestamp values
    plot.add_segment(pd_start, pd_stop, uid=pd_oid)
    assert 2 == len(update_spy)
    assert 2 == len(plot._segments)
    lfr_grp = plot._segments[pd_oid]
    assert _rows == len(lfr_grp._segments)

    # Test adding segment with no signal emission
    plot.add_segment(ts_start + 2000, ts_stop + 2000, emit=False)
    assert 2 == len(update_spy)


def test_LineSelectPlot_remove_segment():
    _rows = 2
    plot = LineSelectPlot(rows=_rows)
    update_spy = QSignalSpy(plot.sigSegmentChanged)

    lfr_oid = OID(tag='segment selection')
    lfr_start = datetime.now().timestamp()
    lfr_end = lfr_start + 300

    plot.add_segment(lfr_start, lfr_end, uid=lfr_oid)
    assert 1 == len(update_spy)
    assert isinstance(update_spy[0][0], LineUpdate)

    assert 1 == len(plot._segments)
    group = plot._segments[lfr_oid]
    assert group._segments[0] in plot.get_plot(row=0).items
    assert group._segments[1] in plot.get_plot(row=1).items

    group.delete()
    assert 0 == len(plot._segments)


def test_LineSelectPlot_set_label(gravity: pd.Series):
    plot = LineSelectPlot(rows=2)
    update_spy = QSignalSpy(plot.sigSegmentChanged)
    plot.add_series(gravity, 0)

    uid = OID()
    plot.add_segment(2, 4, uid=uid)
    assert 1 == len(update_spy)

    segment_grp = plot._segments[uid]
    segment0 = segment_grp._segments[0]
    segment1 = segment_grp._segments[1]

    assert isinstance(segment0, LinearSegment)
    assert '' == segment0._label.textItem.toPlainText()
    assert '' == segment0.label_text

    _label = 'Flight-1'
    segment_grp._update_label(_label)
    assert 2 == len(update_spy)
    update = update_spy[1][0]
    assert _label == update.label
    assert _label == segment0._label.textItem.toPlainText()
    assert _label == segment1._label.textItem.toPlainText()


def test_LineSelectPlot_check_proximity(gravdata):
    _rows = 2
    plot = LineSelectPlot(rows=_rows)
    p0 = plot.get_plot(0)
    plot.add_series(gravdata['gravity'], 0)

    lfr_start = gravdata.index[0]
    lfr_end = gravdata.index[2]
    p0xlim = plot.get_xlim(0)
    span = p0xlim[1] - p0xlim[0]

    xpos = gravdata.index[3].value
    assert plot._check_proximity(xpos, span)

    plot.add_segment(lfr_start, lfr_end)

    assert not plot._check_proximity(xpos, span, proximity=0.2)
    xpos = gravdata.index[4].value
    assert plot._check_proximity(xpos, span, proximity=0.2)


def test_LineSelectPlot_clear():
    pass
