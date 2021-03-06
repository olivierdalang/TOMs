#-----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#---------------------------------------------------------------------
# Tim Hancock/Matthias Kuhn 2017

from qgis.PyQt.QtCore import (
    QObject,
    QDate,
    pyqtSignal
)

from qgis.PyQt.QtWidgets import (
    QMessageBox,
    QAction
)

from qgis.core import (
    QgsMessageLog, QgsFeature, QgsGeometry,
    QgsFeatureRequest,
    QgsRectangle, QgsExpression
)

from ..proposalTypeUtilsClass import ProposalTypeUtilsMixin

#from .TOMsProposalElement import *
from ..core.TOMsProposal import (TOMsProposal)

from ..constants import (
    ProposalStatus,
    RestrictionAction
)

class TOMsTile(QObject):
    def __init__(self, proposalsManager, tileNr=None):
        QObject.__init__(self)

        self.proposalsManager = proposalsManager
        self.tableNames = self.proposalsManager.tableNames

        self.setTilesLayer()

        if tileNr is not None:
            self.setTile(tileNr)

    def setTilesLayer(self):
        self.tilesLayer = self.tableNames.setLayer("MapGrid")
        if self.tilesLayer is None:
            QgsMessageLog.logMessage("In TOMsProposal:setTilesLayer. tilesLayer layer NOT set !!!", tag="TOMs panel")
        QgsMessageLog.logMessage("In TOMsProposal:setTilesLayer... ", tag="TOMs panel")

        self.tilesInAcceptedProposalsLayer = self.tableNames.setLayer("TilesInAcceptedProposals")
        if self.tilesLayer is None:
            QgsMessageLog.logMessage("In TOMsProposal:setTilesLayer. tilesInAcceptedProposalsLayer layer NOT set !!!", tag="TOMs panel")
        QgsMessageLog.logMessage("In TOMsProposal:setTilesLayer... tilesInAcceptedProposalsLayer ", tag="TOMs panel")

    def setTile(self, tileNr):

        self.thisTileNr = tileNr
        self.setTilesLayer()

        if (tileNr is not None):
            query = '\"tileNr\" = {tileNr}'.format(proposalID=tileNr)
            request = QgsFeatureRequest().setFilterExpression(query)
            for tile in self.tilesLayer.getFeatures(request):
                self.thisTile = tile  # make assumption that only one row
                return True

        return False # either not found or 0

    def tile(self):
        return self

    def tileNr(self):
        return self.thisTileNr

    def revisionNr(self):
        return self.thisTile.attribute("RevisionNr")

    def setRevisionNr(self, value):
        return self.thisTile.setAttribute("RevisionNr", value)

    def lastRevisionDate(self):
        return self.thisTile.attribute("LastRevisionDate")

    def setLastRevisionDate(self, value):
        return self.thisTile.setAttribute("LastRevisionDate", value)

    def getTileRevisionNrAtDate(self, filterDate=None):

        QgsMessageLog.logMessage("In TOMsTile:getTileRevisionNrAtDate.", tag="TOMs panel")

        if filterDate is None:
            filterDate = self.proposalsManager.date()

        #query2 = '"tile" = \'{tileid}\''.format(tileid=currTile)

        queryString = "\"TileNr\" = " + str(self.thisTileNr)

        QgsMessageLog.logMessage("In getTileRevisionNrAtDate: queryString: " + str(queryString), tag="TOMs panel")

        expr = QgsExpression(queryString)

        # Grab the results from the layer
        features = self.tilesInAcceptedProposalsLayer.getFeatures(QgsFeatureRequest(expr))
        tileProposal = TOMsProposal(self)

        for feature in sorted(features, key=lambda f: f[2], reverse=True):
            lastProposalID = feature["ProposalID"]
            lastRevisionNr = feature["RevisionNr"]

            tileProposal.setProposal(lastProposalID)

            #lastProposalOpendate = self.proposalsManager.getProposalOpenDate(lastProposalID)
            lastProposalOpendate = tileProposal.getProposalOpenDate()

            QgsMessageLog.logMessage(
                "In getTileRevisionNrAtDate: last Proposal: " + str(lastProposalID) + "; " + str(lastRevisionNr),
                tag="TOMs panel")

            QgsMessageLog.logMessage(
                "In getTileRevisionNrAtDate: last Proposal open date: " + str(lastProposalOpendate) + "; filter date: " + str(filterDate),
                tag="TOMs panel")

            if lastProposalOpendate <= filterDate:
                QgsMessageLog.logMessage(
                    "In getTileRevisionNrAtDate: using Proposal: " + str(lastProposalID) + "; " + str(lastRevisionNr),
                    tag="TOMs panel")
                return lastRevisionNr, lastProposalOpendate

        return 0, None

    def updateTileRevisionNr(self):

        QgsMessageLog.logMessage(
            "In TOMsTile:updateTileRevisionNr. tile" + str(self.thisTileNr) + " currRevNr: ", tag="TOMs panel")

        # This will update the revision numberwithin "Tiles" and add a record to "TilesWithinAcceptedProposals"

        currProposal = self.proposalsManager.currentProposalObject()

        # check that there are no revisions beyond this date
        if self.lastRevisionDate < currProposal.getProposalOpenDate():
            QgsMessageLog.logMessage(
                "In updateTileRevisionNr. tile" + str(self.thisTileNr) + " revision numbers are out of sync",
                tag="TOMs panel")
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("In updateTileRevisionNr. tile" + str(self.thisTileNr) + " revision numbers are out of sync"))
            return False

        if self.revisionNr() is None:
            newRevisionNr = 1
        else:
            newRevisionNr = self.revisionNr() + 1

        self.setRevisionNr(newRevisionNr)
        self.setLastRevisionDate(currProposal.getProposalOpenDate())

        # Now need to add the details of this tile to "TilesWithinAcceptedProposals" (including revision numbers at time of acceptance)

        newRecord = QgsFeature(self.tilesInAcceptedProposalsLayer.fields())

        idxProposalID = self.tilesInAcceptedProposalsLayer.fields().indexFromName("ProposalID")
        idxTileNr = self.tilesInAcceptedProposalsLayer.fields().indexFromName("TileNr")
        idxRevisionNr = self.tilesInAcceptedProposalsLayer.fields().indexFromName("RevisionNr")

        newRecord[idxProposalID] = currProposal.getProposalNr()
        newRecord[idxTileNr] = self.thisTileNr
        newRecord[idxRevisionNr] = newRevisionNr
        newRecord.setGeometry(QgsGeometry())

        status = self.tilesInAcceptedProposalsLayer.addFeature(newRecord)

        return status


